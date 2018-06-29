#!env python3
#
import  argparse
from    functools   import partial
import  json
import  logging
import  redis
import  sys
from    tqdm        import tqdm

log = logging.getLogger('loadredditdata')

def main():
    args = get_arguments()

    redisdb = redis.StrictRedis(db = 0)
    subreddit_filter = partial(is_from_subreddit, args.subreddit)
    load = partial(load_reddit_archive, redisdb, subreddit_filter)

    for name, didsucceed, msg in map(load, args.files):
        if didsucceed:
            log.info('File %s was loaded successfully.', name)
        else:
            log.error('File %s failed to load.', name)

def load_reddit_archive(redisdb, subreddit_filter, filename):
    from os.path import basename
    from itertools import islice
    log = log.getChild('load_reddit_archive')

    try:
        archive, process = open_archive(filename)
        reddit_content = map(json.loads, line_iterator(archive))
        subreddit_content = filter(subreddit_filter, reddit_content)

        for content in islice(subreddit_content, 0, 1):
            if 'title' in content:
                log.info('Assuming %s contains submissions.', filename)
                store_post(redisdb, content)
                for content in tqdm(subreddit_content):
                    store_post(redisdb, content)
            else:
                log.info('Assuming %s contains comments.', filename)
                store_comment(redisdb, content)
                for content in tqdm(subreddit_content):
                    store_comment(redisdb, content)

        process.wait()

    except Exception as error:
        return (basename(filename), False, str(error))
    return (basename(filename), True, '')

def store_post(db, post):
    name = 't3_{}'.format(post['id'])

    # Properties of post that we care about.
    db.hset(name, 'date', post['created_utc'])
    db.hset(name, 'author', post['author'])
    db.hset(name, 'score', post['score'])
    db.hset(name, 'link_to', post['permalink'])
    db.hset(name, 'flair', post['link_flair_text'])

    # Make sure to add both the post and user to a global set.
    db.sadd('posts', name)
    db.sadd('users', post['author'])

def store_comment(db, comment):
    name = 't1_{}'.format(comment['id'])
    parent_post_set = '{}:comments'.format(comment['link_id'])

    # properties we need to know about comments.
    db.hset(name, 'date', comment['created_utc'])
    db.hset(name, 'parent', comment['parent_id'])
    db.hset(name, 'author', comment['author'])
    db.hset(name, 'author_flair', comment['author_flair_text'])
    db.hset(name, 'score', comment['score'])

    # Add comment to post comment set, and also the author to the set.
    db.sadd(parent_post_set, name)
    db.sadd('users', comment['author'])

def is_from_subreddit(subreddit, jsobj):
    if jsobj['subreddit_id'] == None:
        # Unidentified Subreddit, don't count it.
        return False

    return jsobj['subreddit'] == subreddit

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

    log = log.getChild('open_archive')

    XZ = ['xz', '-dc', '-T', '0', filename]
    BZ2 = ['bzip2', '-dc', filename]
    Run = partial(sp.Popen, bufsize = 1024 * 1024 * 128, stdout = sp.PIPE, stdin = sp.DEVNULL, stderr = sp.DEVNULL)

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