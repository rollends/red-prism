class GraphDescriptor:
    def __init__(self):
        self.node_count = 0
        self._node_to_id = list()
        self._id_to_node = dict()
        self.posts = set()
        self.users = set()
        self._comments_on_post = dict()

    def enumerate_posts(self):
        return zip(
            map(self.node_index_from_name, self.posts),
            self.posts
        )

    def enumerate_users(self):
        return zip(
            map(self.node_index_from_name, self.users),
            self.users
        )

    def enumerate_comments_on(self, post_name):
        comment_set = self.comments_on(post_name)
        return zip(
            map(self.node_index_from_name, comment_set),
            comment_set
        )

    def node_index_from_name(self, name):
        return self._id_to_node[name]

    def name_from_node_index(self, nodeind):
        return self._node_to_id[nodeind]

    def comments_on(self, post_name):
        if post_name not in self._comments_on_post:
            return set()
        return self._comments_on_post[post_name]

    def add_post_node(self, name):
        assert(isinstance(name, str))
        self.posts.add(name)
        self.add_node(name)

    def add_user_node(self, name):
        assert(isinstance(name, str))
        self.users.add(name)
        self.add_node(name)

    def add_comment_to_post(self, postname, comment):
        assert(isinstance(postname, str))
        assert(isinstance(comment, str))

        self.add_node(comment)

        if postname not in self._comments_on_post:
            self._comments_on_post[postname] = set()

        self._comments_on_post[postname].add(comment)

    def add_node(self, name):
        assert(isinstance(name, str))
        self._id_to_node[name] = len(self._node_to_id)
        self._node_to_id.append(name)
        self.node_count = len(self._node_to_id)