#coding=utf-8
'''
Author: Weiping Song
Contact: Weiping Song
'''

import pandas as pd
import numpy as np
import random
import os
import json
import datetime as dt
from collections import Counter

data_path = 'data/'

class Dictionary(object):
    def __init__(self):
        self.item2idx = {}
        self.idx2item = []
        self.counter = Counter()

    def add_item(self, item):
        self.counter[item] +=1

    def prep_dict(self):
        for item in self.counter:
            if item not in self.item2idx:
                self.idx2item.append(item)
                self.item2idx[item] = len(self.idx2item)

    def __len__(self):
        return len(self.idx2item)


class Corpus(object):
    def __init__(self, ItemId):
        self.dict = Dictionary()
        for item in ItemId:
            self.dict.add_item(item)
        self.dict.prep_dict()

def data_generator(args):
    '''

    :param args:
    :return:
    '''
    path_to_data= data_path + args.data + '/'

    # if data dictionaries have not been created yet...
    if not os.path.exists(path_to_data + args.data + '_train_tr.json'):

        # read train, validation and test data
        tr_df = pd.read_csv(path_to_data + args.data + '_train_tr.txt', sep='\t')
        val_df = pd.read_csv(path_to_data + args.data + '_train_valid.txt', sep='\t')
        test_df = pd.read_csv(path_to_data + args.data + '_test.txt', sep='\t')


        corpus_item = Corpus(tr_df['ItemId'])
        corpus_user = Corpus(tr_df['UserId'])

        # save item and user dicts
        np.save(path_to_data + args.data + '_item_dict', np.asarray(corpus_item.dict.idx2item))
        np.save(path_to_data + args.data + '_user_dict', np.asarray(corpus_user.dict.idx2item))

        tr = tr_df.sort_values(['UserId', 'Time']).groupby('UserId')['ItemId'].apply(list).to_dict()
        val = val_df.sort_values(['UserId', 'Time']).groupby('UserId')['ItemId'].apply(list).to_dict()
        test = test_df.sort_values(['UserId', 'Time']).groupby('UserId')['ItemId'].apply(list).to_dict()

        # for each data set convert items to index for each user, then write out json dictionary
        _ = prepare_data(corpus_item, corpus_user, tr, args.data + '_train_tr', path_to_data)
        _ = prepare_data(corpus_item, corpus_user, val, args.data + '_train_valid',path_to_data)
        _ = prepare_data(corpus_item, corpus_user, test, args.data + '_test', path_to_data)

    # load data dictionaries
    with open(path_to_data + args.data + '_train_tr.json', 'r') as fp:
        train_data = json.load(fp)
    with open(path_to_data + args.data + '_train_valid.json', 'r') as fp:
        val_data = json.load(fp)
    with open(path_to_data + args.data + '_test.json', 'r') as fp:
        test_data = json.load(fp)

    # load lookup tables
    item2idx = np.load(path_to_data + args.data + '_item_dict.npy')
    user2idx = np.load(path_to_data + args.data + '_user_dict.npy')
    n_items = item2idx.size
    n_users = user2idx.size
    
    return [train_data, val_data, test_data, n_items, n_users]

def prepare_data(corpus_item, corpus_user, data, dname, path_to_data):
    '''
    Convert items to index for all users and dump out as json dict.
    :param corpus_item:
    :param corpus_user:
    :param data:
    :param dname:
    :param path_to_data:
    :return:
    '''
    ret = {}
    user_str_ids = data.keys()
    # loop over users
    for u in user_str_ids:
        u_int_id = corpus_user.dict.item2idx[u]
        i_int_ids = []
        item_str_ids = data[u]
        for i in item_str_ids:
            i_int_ids.append(corpus_item.dict.item2idx[i])
        ret[u_int_id] = i_int_ids
    with open(path_to_data + dname + '.json', 'w') as fp:
        json.dump(ret, fp)

    return ret

def prepare_eval_test(data, batch_size, max_test_len=100):
    '''
    
    :param data:
    :param batch_size:
    :param max_test_len:
    :return:
    '''
    if batch_size < 2:
        batch_size = 2
    uids = data.keys()
    all_u = []
    all_inp = []
    all_pos = []
    for u in uids:
        all_u.append(int(u))
        itemids = data[u]
        inp = np.zeros([max_test_len], dtype=np.int32)
        pos = np.zeros([max_test_len], dtype=np.int32)
        l = min(max_test_len, len(itemids))
        inp[:l] = itemids[:l]
        pos[:l-1] = itemids[1:l]
        all_inp.append(inp)
        all_pos.append(pos)

    num_batches = int(len(all_u) / batch_size)
    batches = []
    for i in range(num_batches):
        batch_u = all_u[i*batch_size: (i+1)*batch_size]
        batch_inp = all_inp[i*batch_size: (i+1)*batch_size]
        batch_pos = all_pos[i*batch_size: (i+1)*batch_size]
        batches.append((batch_u, batch_inp, batch_pos))
    if num_batches * batch_size < len(all_u):
        batches.append((all_u[num_batches * batch_size:], all_inp[num_batches * batch_size:], all_pos[num_batches * batch_size:]))
        
    return batches

def preprocess_session(dname):
    '''
    The model can be applied for session-based recommendation, where a sequence is seen as a user's history.
    The data should contain three columns, i.e., SessionId, ItemId and Time with Tab as separator.
    '''
    data = pd.read_csv(data_path + dname + '/' + dname + '.tsv', sep='\t', header=None)
    data.columns = ['SessionId', 'ItemId', 'Time']
    session_lengths = data.groupby('SessionId').size()
    data = data[np.in1d(data.SessionId, session_lengths[session_lengths>2].index)]
    
    item_supports = data.groupby('ItemId').size()
    data = data[np.in1d(data.ItemId, item_supports[item_supports>=10].index)]
    print('Unique items: {}'.format(data.ItemId.nunique()))
        
    session_lengths = data.groupby('SessionId').size()
    print('Average session length: {}'.format(session_lengths.mean()))
    data = data[np.in1d(data.SessionId, session_lengths[session_lengths>2].index)]
    
    session_lengths = data.groupby('SessionId').size()
    print('Average session length after removing sessions with less than two event: {}'.format(session_lengths.mean()))
    
    session_max_times = data.groupby('SessionId').Time.max()
    tmax = data.Time.max()
    session_train = session_max_times[session_max_times < tmax-86400*2].index # We preserve sessions of last two days as validation and test data
    session_test = session_max_times[session_max_times >= tmax-86400*2].index
    train = data[np.in1d(data.SessionId, session_train)]
    test = data[np.in1d(data.SessionId, session_test)]
    test = test[np.in1d(test.ItemId, train.ItemId)]
    
    tslength = test.groupby('SessionId').size()
    test = test[np.in1d(test.SessionId, tslength[tslength>2].index)]

    test_session = test.SessionId.unique()
    test_session_ = np.random.choice(test_session, int(len(test_session) / 2), replace=False)
    test_ = test.loc[test['SessionId'].isin(test_session_)]
    val_ = test.loc[~test['SessionId'].isin(test_session_)]
    print('Train size: {}'.format(len(train)))
    print('Dev size: {}'.format(len(val_)))
    print('Test size: {}'.format(len(test_)))

    columns = ['SessionId', 'ItemId', 'Time']
    header = ['UserId', 'ItemId', 'Time']
    train.to_csv(data_path + dname + '/' + dname + '_train_tr.txt', sep='\t', columns=columns, header=header, index=False)
    test_.to_csv(data_path + dname + '/' + dname + '_test.txt', sep='\t',columns=columns, header=header, index=False)
    val_.to_csv(data_path + dname + '/' + dname + '_train_valid.txt', sep='\t', columns=columns, header=header, index=False)


def preprocess_sequence(dname):
    '''
    For sequential recommendation.
    The data should contain three columns, i.e., user, item and Time with Tab as separator.
    '''
    data = pd.read_csv(data_path + dname + '/' + dname + '.tsv', sep='\t', header=None)
    data.columns = ['user', 'item', 'Time']
    
    event_lengths = data.groupby('user').size()
    print('Average check-ins per user: {}'.format(event_lengths.mean()))
    data = data[np.in1d(data.user, event_lengths[event_lengths>10].index)]
    
    item_supports = data.groupby('item').size()
    # 50 for delicious, 10 for gowalla
    data = data[np.in1d(data.item, item_supports[item_supports>=10].index)]
    print('Unique items: {}'.format(data.item.nunique()))
    
    event_lengths = data.groupby('user').size()
    data = data[np.in1d(data.user, event_lengths[event_lengths>=10].index)]
    
    event_lengths = data.groupby('user').size()
    print('Average check-ins per user after removing sessions with one event: {}'.format(event_lengths.mean()))
    
    tmin = data.Time.min()
    tmax = data.Time.max()
    pivot = (tmax-tmin) * 0.9 + tmin # Preserve last 10% as validation and test data
    train = data.loc[data['Time'] < pivot]
    test = data.loc[data['Time'] >= pivot]

    tr_event_lengths = train.groupby('user').size()
    train = train[np.in1d(train.user, tr_event_lengths[tr_event_lengths>3].index)]
    print('Average (train) check-ins per user: {}'.format(tr_event_lengths.mean()))

    user_to_predict = train.user.unique()
    test = test[test['user'].isin(user_to_predict)]
    item_to_predict = train.item.unique()
    test = test[test['item'].isin(item_to_predict)]
    test_event_lengths = test.groupby('user').size()
    test = test[np.in1d(test.user, test_event_lengths[test_event_lengths>3].index)]
    print('Average (test) check-ins per user: {}'.format(test_event_lengths.mean()))

   
    test_user = test.user.unique()
    test_user_ = np.random.choice(test_user, int(len(test_user) / 2), replace=False)
    test_ = test.loc[test['user'].isin(test_user_)]
    val_ = test.loc[~test['user'].isin(test_user_)]
    print('Train size: {}'.format(len(train)))
    print('Dev size: {}'.format(len(val_)))
    print('Test size: {}'.format(len(test_)))

  
    columns = ['user', 'item', 'Time']
    header = ['UserId', 'ItemId', 'Time']
    train.to_csv(data_path + dname + '/' + dname + '_train_tr.txt', sep='\t', columns=columns, header=header, index=False)
    test_.to_csv(data_path + dname + '/' + dname + '_test.txt', sep='\t',columns=columns, header=header, index=False)
    val_.to_csv(data_path + dname + '/' + dname + '_train_valid.txt', sep='\t', columns=columns, header=header, index=False)

if __name__ == '__main__':
    preprocess_sequence('gowalla')


