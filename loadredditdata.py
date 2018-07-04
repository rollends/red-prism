#!env python3
#
import  argparse
from    functools   import partial
import  json
import  logging
import  redis
import  sys
from    tqdm        import tqdm


def main():
    log = logging.getLogger('loadredditdata')
    args = get_arguments()

    redisdb = redis.StrictRedis(db = 0)
    load = partial(load_reddit_archive, redisdb, args.subreddit)

    for name, didsucceed, msg in map(load, args.files):
        if didsucceed:
            log.info('File %s was loaded successfully.', name)
        else:
            log.error('File %s failed to load.', name)

def load_reddit_archive(redisdb, subreddit, filename):
    from os.path import basename
    from itertools import islice

    log = logging.getLogger('load_reddit_archive')

    subreddit_fast_filter = lambda s: s.lower().find(subreddit.lower()) >= 0
    subreddit_filter = partial(is_from_subreddit, subreddit)

    store_post, store_comment = get_store_methods(redisdb, subreddit)
    try:
        # Open archive also gives access to the process that does
        # the decompression for us. This happens to be faster than
        # python probably just due to concurrent operation.
        archive, process = open_archive(filename)

        # Take the line-by-line stream of json strings, and first filter
        # out content that we know definitely is not our concern (doesn't
        # contain the subreddit name)
        fast_filtered_content = filter(subreddit_fast_filter, line_iterator(archive))

        # Then convert the reduced set into json objects.
        reddit_content = map(json.loads, fast_filtered_content)

        # Finally filter out those json objects that _actually_ pertain
        # to our sub of concern.
        subreddit_content = filter(subreddit_filter, reddit_content)

        for content in islice(subreddit_content, 0, 1):
            # Assume the file has only comments, or only submissions but
            # not both! This allows us to not waste time branching unnecessarily
            # by inspecting the first item.
            if 'title' in content:
                log.info('Assuming %s contains submissions.', filename)
                store_post(content)
                for content in tqdm(subreddit_content):
                    store_post(content)
            else:
                log.info('Assuming %s contains comments.', filename)
                store_comment(content)
                for content in tqdm(subreddit_content):
                    store_comment(content)

        process.wait()

    except Exception as error:
        return (basename(filename), False, str(error))
    return (basename(filename), True, '')

def get_store_methods(db, subreddit):
    post_set = '{}_posts'.format(subreddit)
    user_set = '{}_users'.format(subreddit)

    def store_post(post):
        name = 't3_{}'.format(post['id'])

        with db.pipeline() as transaction:
            # Properties of post that we care about.
            transaction.hset(name, 'date', post['created_utc'])
            transaction.hset(name, 'author', post['author'])
            transaction.hset(name, 'score', post['score'])
            transaction.hset(name, 'link_to', post['permalink'])
            transaction.hset(name, 'flair', post['link_flair_text'])

            # Make sure to add both the post and user to a global set.
            transaction.sadd(post_set, name)
            transaction.sadd(user_set, post['author'])
            transaction.execute()

    def store_comment(comment):
        name = 't1_{}'.format(comment['id'])
        parent_post_set = '{}:comments'.format(comment['link_id'])

        with db.pipeline() as transaction:
            # properties we need to know about comments.
            transaction.hset(name, 'date', comment['created_utc'])
            transaction.hset(name, 'parent', comment['parent_id'])
            transaction.hset(name, 'author', comment['author'])
            transaction.hset(name, 'author_flair', comment['author_flair_text'])
            transaction.hset(name, 'score', comment['score'])

            # Add comment to post comment set, and also the author to the set.
            transaction.sadd(parent_post_set, name)
            transaction.sadd(user_set, comment['author'])
            transaction.execute()

    return (store_post, store_comment)

def is_from_subreddit(subreddit, jsobj):
    if jsobj['subreddit_id'] == None:
        # Unidentified Subreddit, don't count it.
        return False

    return jsobj['subreddit'].lower() == subreddit.lower()

def line_iterator(stream):
    from io import TextIOWrapper

    text_stream = TextIOWrapper(stream)

    while text_stream.readable():
        line = text_stream.readline().strip()
        if len(line) == 0:
            break
        yield line

def open_archive(filename):
    import os.path as path
    import subprocess as sp

    log = logging.getLogger('open_archive')

    # Parallel XZ and standard Bzip.
    XZ = ['xz', '-dc', '-T', '0', filename]
    BZ2 = ['bzip2', '-dc', filename]

    # Execution setup. 1GB buffer for stdout, other pipes are left to /dev/null.
    Run = partial(sp.Popen, bufsize = 1024 * 1024 * 1024, stdout = sp.PIPE, stdin = sp.DEVNULL, stderr = sp.DEVNULL)

    _, extension = path.splitext(filename)

    if extension.lower() == '.xz':
        log.info('Opening %s archive as an XZ file.', filename)
        process = Run(XZ)
    elif extension.lower() == '.bz2':
        log.info('Opening %s archive as an Bzip2 file.', filename)
        process = Run(BZ2)
    else:
        log.error('Could not determine what type of archive %s is.', filename)
        raise Exception("Extension {} wasn't expected.".format(extension))

    return (process.stdout, process)

def get_arguments():
    parser = argparse.ArgumentParser(description = '''
        Takes data from the Reddit data dump and
        inserts it into the Redis database.''')
    parser.add_argument(
        'subreddit',
        metavar = 'SUBREDDIT',
        type = str,
        help = 'The subreddit to insert into Redis.'
    )
    parser.add_argument(
        'files',
        metavar = 'REDDIT_ARCHIVE',
        help = 'Reddit archives to load. These must be the compressed files downloaded from https://files.pushshift.io/reddit/.',
        nargs = '+'
    )
    return parser.parse_args()

if __name__ == '__main__':
    logging.basicConfig(
        format='[%(asctime)s] [%(levelname)s] : %(message)s',
        filename='logs/loadredditdata.log',
        level=logging.INFO
    )
    main()
    logging.shutdown()