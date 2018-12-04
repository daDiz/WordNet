import numpy as np


class test_data():
    def __init__(self, rel_file, word_file, out_file, seed=123):
        np.random.seed(seed)
        self._rel_file = rel_file
        self._word_file = word_file
        self._out_file = out_file
        self._rel = None
        self._word = None
        self._id_word = {}
        self._data = []
        self._n = 0
        self._m = 0

    def load(self):
        self._rel = np.loadtxt(self._rel_file, dtype=str, delimiter='\t')
        self._word = np.loadtxt(self._word_file, dtype=str, delimiter='\t')
        self._n = len(self._rel)
        self._m = len(self._word)

        for i in range(self._m):
            idx = self._word[i][1]
            w = self._word[i][0]
            if self._id_word.get(idx):
                self._id_word[idx].append(w)
            else:
                self._id_word[idx] = [w]


    # convert id1_rel_id2 to word1_rel_word2 for num pairs
    def convert(self, num=1000):
        if num > self._n:
            raise Exception("not enough pairs")

        if len(self._data) > 0:
            self._data = []

        for i in range(num):
            idx_rel = self._rel[i]
            idx1 = idx_rel[0]
            rel = idx_rel[1]
            idx2 = idx_rel[2]

            w1 = np.random.choice(self._id_word[idx1])
            w2 = np.random.choice(self._id_word[idx2])

            self._data.append([w1, rel, w2])


    def save_data(self):
        np.savetxt(self._out_file, self._data, fmt='%s', delimiter='\t')


if __name__=="__main__":
    td = test_data("../data/wn18rr/all.txt", "../data/wn18rr/word_id_pair.txt", "../data/wn18rr/test.txt", seed=123)

    td.load()
    td.convert(10000)
    td.save_data()

