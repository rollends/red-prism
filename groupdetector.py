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
    """RedditBasicDigraph(redisdb, filename = None)
    """

    def __init__(self, subreddit, redisdb = None, filename = None):
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

        self._add_post_nodes(subreddit)
        self._add_user_nodes(subreddit)

        # First build the matrix using a fairly mutable representation.
        self.log.info('Constructing sparse (linked-list) matrix of dimension %d.', self.desc.node_count)
        self.A = sparse.lil_matrix( (len(self.desc.users), len(self.desc.users)) )
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

        from scipy.io import savemat
        savemat('experiment/{}.mat'.format(filename), {'A': self.A})

    def _set_initial_weights(self):
        # Find base index of where the users live.
        base_index = min(map(lambda d: d[1], filter(lambda u: u[0] in self.desc.users, self.desc._id_to_node.items())))
        get_user_index = lambda user: self.desc.node_index_from_name(user) - base_index

        for i, post_id in tqdm(self.desc.enumerate_posts(), desc='Adding Post-Related Edges'):
            # The post is influenced by the author, in the same weight as
            # the actual score...
            post_author = bytes.decode(self.db.hget(post_id, 'author'))
            q = get_user_index(post_author)

            pair_set = set();

            # Go through all comments.
            for j, comment_id in self.desc.enumerate_comments_on(post_id):
                comment_parent = bytes.decode(self.db.hget(comment_id, 'parent'))
                comment_author = bytes.decode(self.db.hget(comment_id, 'author'))

                comment_parent_author = bytes.decode(self.db.hget(comment_parent, 'author'))

                # Author influenced by parent commenter
                ci = get_user_index(comment_parent_author)
                cj = get_user_index(comment_author)

                if (cj, ci) not in pair_set:
                    self.A[cj, ci] = self.A[cj, ci] + 1
                    pair_set.add( (cj,ci) )

    def _add_post_nodes(self, subreddit):
        post_stream = map(bytes.decode, self.db.sscan_iter('{}_posts'.format(subreddit)))
        for post_id in tqdm(post_stream, desc='Adding Post Nodes'):
            self.desc.add_post_node(post_id)
            self._add_comment_nodes(post_id)

    def _add_user_nodes(self, subreddit):
        user_stream = map(bytes.decode, self.db.sscan_iter('{}_users'.format(subreddit)))
        for user_id in tqdm(user_stream, desc='Adding User Nodes'):
            self.desc.add_user_node(user_id)

    def _add_comment_nodes(self, post_id):
        assert(isinstance(post_id, str))

        comment_set_id = '{}:comments'.format(post_id)
        comment_stream = map(bytes.decode, self.db.sscan_iter(comment_set_id))
        for comment_id in comment_stream:
            self.desc.add_comment_to_post(post_id, comment_id)

def main():
    import matplotlib.pyplot as pyplot

    parser = argparse.ArgumentParser(description='Builds weighted digraph for analyzing groups on Reddit.')
    parser.add_argument(
        'subreddit',
        metavar = 'SUBREDDIT',
        type = str,
        help = 'The subreddit to insert into Redis.'
    )
    parser.add_argument('--graphfile', required=False, default=None)
    arguments = parser.parse_args()

    if arguments.graphfile is not None:
        graph = RedditBasicDigraph(arguments.subreddit, filename=arguments.graphfile)
    else:
        graph = RedditBasicDigraph(arguments.subreddit,
                                   redisdb = redis.StrictRedis(db = 0),
                                   filename = 'data/groupdetector-{}'.format(arguments.subreddit))

    #a = graph.katz_centrality()
    #indices = indices[-1:0:-1]

    from pprint import pprint

if __name__ == '__main__':
    logging.basicConfig(
        format='[%(asctime)s] [%(levelname)s] : %(message)s',
        filename='logs/groupdetector.log',
        level=logging.INFO
    )
    main()
    logging.shutdown()