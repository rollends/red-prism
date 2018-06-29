#!env python3
#
import  argparse
from    functools               import  partial
from    itertools               import  chain
import  json
import  matplotlib
import  numpy                   as      np
import  pickle
import  redis
import  scipy                   as      sp
import  scipy.sparse            as      sparse
import  scipy.sparse.linalg     as      sparse_linalg
import  sys
from    tqdm                    import  tqdm

class RedditBasicDigraph:
    """A weighted digraph representation of the basic influential relationships
    on Reddit. The representation only models:
        * Self-Influence.
        * Top-Level Comment Influence only.
    """
    class GraphDescriptors:
        def __init__(self):
            self.node_count = 0
            self.node_to_id = list()
            self.id_to_node = dict()
            self.posts = set()
            self.users = set()
            self.comments_on_post = dict()

        def add_node(self, hashv):
            assert(isinstance(hashv, str))
            self.id_to_node[hashv] = len(self.node_to_id)
            self.node_to_id.append(hashv)
            self.node_count = len(self.node_to_id)


    def __init__(self, redisdb, filename=None):
        self.db = redisdb

        if filename is not None:
            with open('{}.dat'.format(filename), 'rb') as file:
                self.desc = pickle.load(file)
            self.A = sparse.load_npz('{}.npz'.format(filename))
            return

        self.desc = RedditBasicDigraph.GraphDescriptors()

        self._add_post_nodes()
        self._add_user_nodes()

        # First build the matrix using a fairly mutable representation.
        self.A = sparse.lil_matrix( (self.desc.node_count, self.desc.node_count) )
        self._set_initial_weights()

        # Convert the matrix now to a more compressed, rigid representation.
        self.A = self.A.tocsr()

        # Save the form to a file.
        with open('influencedetector.dat', 'wb') as file:
            pickle.dump(self.desc, file)
        sparse.save_npz('influencedetector.npz', self.A)

    def _set_initial_weights(self):
        post_enumerator = zip(map(self.desc.id_to_node.get, self.desc.posts), self.desc.posts)
        for i, post_id in tqdm(post_enumerator, desc='Adding Post-Related Edges'):
            # The post is influenced by the author, in the same weight as
            # the actual score...
            post_author = bytes.decode(self.db.hget(post_id, 'author'))
            q = self.desc.id_to_node[post_author]
            self.A[i, q] = 1

            # Go through top level comments.
            for comment_id in self.desc.comments_on_post[post_id]:
                comment_parent = bytes.decode(self.db.hget(comment_id, 'parent'))
                comment_author = bytes.decode(self.db.hget(comment_id, 'author'))

                # Comment influences parent.
                ci = self.desc.id_to_node[comment_parent]
                cj = self.desc.id_to_node[comment_id]
                self.A[ci, cj] = 1

                # Author influences comment
                ci = self.desc.id_to_node[comment_id]
                cj = self.desc.id_to_node[comment_author]
                self.A[ci, cj] = 1

                # Author Influenced by post
                ci = self.desc.id_to_node[comment_author]
                self.A[ci, i] = 1

        # Users influence themselves.
        user_enumerator = zip(map(self.desc.id_to_node.get, self.desc.users), self.desc.users)
        for i, user_id in tqdm(user_enumerator, desc='Adding User Self-Influence Edges'):
            self.A[i, i] = 1

    def _add_post_nodes(self):
        post_stream = self.db.sscan_iter('posts')
        for post_id in tqdm(post_stream, desc='Adding Post Nodes'):
            str_post = bytes.decode(post_id)
            self.desc.posts.add(str_post)
            self.desc.add_node(str_post)
            self._add_comment_nodes(str_post)

    def _add_user_nodes(self):
        user_stream = self.db.sscan_iter('users')
        for user_id in tqdm(user_stream, desc='Adding User Nodes'):
            str_user = bytes.decode(user_id)
            self.desc.users.add(str_user)
            self.desc.add_node(str_user)

    def _add_comment_nodes(self, post_id):
        comment_set_id = '{}:comments'.format(post_id)
        comment_stream = self.db.sscan_iter(comment_set_id)
        comment_set = set()
        for comment_id in comment_stream:
            str_comment = bytes.decode(comment_id)
            self.desc.add_node(str_comment)
            comment_set.add(str_comment)
        self.desc.comments_on_post[post_id] = comment_set

    def _make_row_stochastic(self):
        # Find row sum...normalize with respect to that.
        row_sums = self.A.sum(axis=1)
        self.A = sparse.diags(np.reciprocal(row_sums.flat)) * self.A

    def is_row_stochastic(self):
        # Testing it actually did the thing.
        row_sum = np.array(self.A.sum(axis=1).flat)
        expected_sum = np.ones(row_sum.shape)
        return all(np.isclose(row_sum, expected_sum, 1e-10))

    def dominant_eigenvector(self):
        # Find the dominant eigenvector.
        p, v = sparse_linalg.eigs(self.A.transpose(), k=1, which='LM', tol=0)

        # Normalize the eigenvector, and confirm it has the desired non-negative requirement.
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

    parser = argparse.ArgumentParser(description='Builds weighted digraph in Redis.')
    parser.add_argument('--graphfile', required=False, default=None)
    arguments = parser.parse_args()

    graph = RedditBasicDigraph(redis.StrictRedis(db = 0), filename=arguments.graphfile)

    a = graph.katz_centrality()
    indices = np.argsort(a)
    indices = indices[-1:0:-1]

    from pprint import pprint

    # Top 10 Users
    top10users = list(map(graph.desc.node_to_id.__getitem__, indices[0:50]))
    pprint(top10users)


if __name__ == '__main__':
    main()