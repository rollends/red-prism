#!env python3
#
import  argparse
from    functools               import  partial
from    itertools               import  chain
import  json
import  logging
import  matplotlib
import  numpy                   as      np
import  pickle
import  redis
import  scipy                   as      sp
import  scipy.sparse            as      sparse
import  scipy.sparse.linalg     as      sparse_linalg
import  sys
from    tqdm                    import  tqdm

import  graphhelper

class RedditBasicDigraph:
    """
    :class:: RedditBasicDigraph(redisdb, filename = None)

        A digraph representation of the basic influential relationships
        on Reddit. The model has the following edges:
          * Submissions are influenced by submitting user.
          * Submissions are influenced by comments.
          * Comments are influenced by author and by child comments.
          * Commenter is influenced by parent post.
        The edges are weighted equally, so any centrality algorithm will
        be effectively detecting the number of interactions as opposed
        to their quality.

        :attribute:: db

            StrictRedis instance.

        :attribute:: A

            (Sparse) Adjacency matrix representing the weighted
            digraph.

        :attribute:: desc

            RedisBasicDigraph.GraphDescriptors instance. Provides
            mappings between indices of the state space and the
            actual Reddit ids (t3_*, t1_*, and user names).

    """

    def __init__(self, redisdb = None, filename = None):
        self.log = logging.getLogger(self.__class__.__name__)

        config_file = '{}.dat'.format(filename)
        mat_file = '{}.npz'.format(filename)
        if redisdb is None:
            assert(filename is not None)

            self.log.info('Loading digraph data from %s.', config_file)

            with open(config_file, 'rb') as file:
                self.desc = pickle.load(file)

            self.log.info('Loading digraph adjacency matrix from %s.', mat_file)
            self.A = sparse.load_npz(mat_file)
            return

        self.log.info('Building Digraph directly from Redis.')

        self.db = redisdb
        self.desc = graphhelper.GraphDescriptor()

        self._add_post_nodes()
        self._add_user_nodes()

        # First build the matrix using a fairly mutable representation.
        self.log.info('Constructing sparse (linked-list) matrix.')
        self.A = sparse.lil_matrix( (self.desc.node_count, self.desc.node_count) )
        self._set_initial_weights()

        # Convert the matrix now to a more compressed, rigid representation.
        self.log.info('Convert adjacency matrix into compressed sparse row representation.')
        self.A = self.A.tocsr()

        # Save the form to a file.
        self.log.info('Saving digraph data into %s.', config_file)
        with open(config_file, 'wb') as file:
            pickle.dump(self.desc, file)
        self.log.info('Saving digraph adjacency matrix into %s.', mat_file)
        sparse.save_npz(mat_file, self.A)

    def _set_initial_weights(self):
        for i, post_id in tqdm(self.desc.enumerate_posts(), desc='Adding Post-Related Edges'):
            # The post is influenced by the author, in the same weight as
            # the actual score...
            post_author = bytes.decode(self.db.hget(post_id, 'author'))
            q = self.desc.node_index_from_name(post_author)
            self.A[i, q] = 1

            # Go through all comments.
            for j, comment_id in self.desc.enumerate_comments_on(post_id):
                comment_parent = bytes.decode(self.db.hget(comment_id, 'parent'))
                comment_author = bytes.decode(self.db.hget(comment_id, 'author'))

                # Comment influences parent.
                ci = self.desc.node_index_from_name(comment_parent)
                self.A[ci, j] = 1

                # Author influences comment
                cj = self.desc.node_index_from_name(comment_author)
                self.A[j, cj] = 1

                # Author Influenced by post
                ci = self.desc.node_index_from_name(comment_author)
                self.A[ci, i] = 1

        # Users influence themselves.
        for i, _ in tqdm(self.desc.enumerate_users(), desc='Adding User Self-Influence Edges'):
            self.A[i, i] = 1

    def _add_post_nodes(self):
        post_stream = map(bytes.decode, self.db.sscan_iter('posts'))
        for post_id in tqdm(post_stream, desc='Adding Post Nodes'):
            self.desc.add_post_node(post_id)
            self._add_comment_nodes(post_id)

    def _add_user_nodes(self):
        user_stream = map(bytes.decode, self.db.sscan_iter('users'))
        for user_id in tqdm(user_stream, desc='Adding User Nodes'):
            self.desc.add_user_node(user_id)

    def _add_comment_nodes(self, post_id):
        assert(isinstance(post_id, str))

        comment_set_id = '{}:comments'.format(post_id)
        comment_stream = map(bytes.decode, self.db.sscan_iter(comment_set_id))
        for comment_id in comment_stream:
            self.desc.add_comment_to_post(post_id, comment_id)

    def is_row_stochastic(self):
        # Testing it actually did the thing.
        row_sum = np.array(self.A.sum(axis=1).flat)
        expected_sum = np.ones(row_sum.shape)
        return all(np.isclose(row_sum, expected_sum, 1e-10))

    def dominant_eigenvector(self):
        # Find the dominant eigenvector.
        p, v = sparse_linalg.eigs(self.A.transpose(), k=1, which='LM', tol=0)

        # Normalize the eigenvector
        v = v[:,0] / sum(v[:, 0])

        return np.array(v.flat)

    def katz_centrality(self):
        ones = np.ones( (self.A.shape[0], 1) )
        ck1 = np.zeros( (self.A.shape[0], 1) )

        p = sparse_linalg.eigs(self.A, k=1, which='LM', tol=0, return_eigenvectors=False)
        alpha = 1.0 / (2 * np.abs(p))

        while True:
            ck2 = alpha * self.A.dot(ck1 + ones)
            if all(np.isclose(ck1, ck2, 1e-9)):
                return np.array(ck2.flat)
            ck1 = ck2

def main():
    import matplotlib.pyplot as pyplot

    lg = logging.getLogger('influencedetector')

    parser = argparse.ArgumentParser(description='Builds weighted digraph in Redis.')
    parser.add_argument('--graphfile', required=False, default=None)
    arguments = parser.parse_args()

    if arguments.graphfile is not None:
        graph = RedditBasicDigraph(filename=arguments.graphfile)
    else:
        graph = RedditBasicDigraph(redisdb = redis.StrictRedis(db = 0),
                                   filename = 'data/influencedetector')

    a = graph.katz_centrality()
    indices = np.argsort(a)
    indices = indices[-1:0:-1]

    from pprint import pprint

    # Top 10 Users
    top10users = list(map(graph.desc.name_from_node_index, indices[0:50]))
    pprint(top10users)


if __name__ == '__main__':
    logging.basicConfig(
        format='[%(asctime)s] [%(levelname)s] : %(message)s',
        filename='logs/influencedetector.log',
        level=logging.INFO
    )
    main()
    logging.shutdown()