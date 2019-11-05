# library imports

import time
import sys
import pandas as pd
import os
import shutil
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import category_encoders as ce
from itertools import combinations
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import PolynomialFeatures
from IPython.display import clear_output
from IPython.display import display
from collections import Counter

# initialization

recycle = pd.DataFrame()
checkpoint_ = {}

class WorkSpace:
    """
    Create and manage a basic Worksspace.
    Creates a folder tree of data, notebooks,submission files.
    """

    def __init__(self, files):
        self.trainWS = files[0]
        self.testWS = files[1]
        self.submissionWS = files[2]

    def create(self, move=False):
        try:
            os.mkdir('data')
            os.mkdir('notebooks')
            os.mkdir('submissions')
        except:
            print('Error Making Directories')
            pass
        if move:
            try:
                shutil.move(self.trainWS, 'data')
                shutil.move(self.testWS, 'data')
                shutil.move(self.submissionWS, 'data')
            except:
                print('Error moving files..')


class DataObjects:
    """Initializing the Dataobjects
    arg:
    train: train DataFrame
    test:  test DataFrame
    submission: Sample Submission Data Frame
    data: Merged train and test
    """

    def __init__(self):
        self.train = None
        self.test = None
        self.submission = None
        self.data = None
        self.encoded_data = None
        self.categories = None
        self.bundle = None
        self.checkpoint_ = {}

    def merge(self, info=True):
        """
        merge two datasets for evaluation
        """
        self.train['source'] = 'train'
        self.test['source'] = 'test'
        self.data = pd.concat([self.train, self.test], ignore_index=True)
        if info:
            print(f'Test Shape: {self.test.shape},\nTrain Shape: {self.train.shape}, \nData Shape: {self.data.shape}')

    def split(self):
        """
        split datasets into train and test
        """
        self.train = self.data[self.data.source == "train"]
        self.test = self.data[self.data.source == "test"]
        print(self.train.shape, self.test.shape)
        del self.train['source']
        del self.test['source']
        return self.train, self.test

    def checkpoint(self, save=False, index=0):
        """
        creates a checkpoint with the option of saving to the disk
        """
        try:
            os.mkdir('checkpoints')
        except:
            print('No New Directory was made..')
        self.checkpoint_.update({(f'checkpoint{len(self.checkpoint_)}'): self.data})
        print('New Checkpoint Created')
        if save:
            self.data.to_csv(f"checkpoints/Checkpoint{len(os.listdir('checkpoints'))}.csv", index=None)

    def checkpoints(self, restore=None, load=False):
        """ restores a previous saved checkpoint!"""
        if load:
            file_ = []
            for csv in os.listdir('checkpoints'):
                file_.append(pd.read_csv('checkpoints/' + csv))
            for csv in file_:
                self.checkpoint_.update({('checkpoint{}f'.format(len(self.checkpoint_), )): csv})
        if restore is None:
            print(self.checkpoint_.keys())
        if restore is not None:
            self.data = self.checkpoint_[restore]

    def encodings(self, one_hot=False, catboost=True):
        self.encoded_data = self.data
        cat_feats = [column for column in self.encoded_data.select_dtypes(include='object').columns]
        if (one_hot == False) & (catboost == True):
            extra = [column for column in self.encoded_data.select_dtypes(
                include='int64').columns if len(self.encoded_data[column].unique()) < 10]
            cat_feats.extend(extra)
            self.categories = cat_feats
            self.categories.remove('source')
        if (one_hot == False) & (catboost == False):
            for column in cat_feats:
                self.catcode(column, encoded=True)
        if (one_hot == True) & (catboost == False):
            for column in cat_feats:
                self.encoded_data = pd.concat(
                    [self.encoded_data, pd.get_dummies(self.encoded_data[column], prefix=column)], 1)
                self.encoded_data.drop(column, axis=1, inplace=True)

    def bundles(self, verbose=False):
        """
        this creates a bundle of the train and test set, almost similar to a catboost pool method
        """
        if verbose:
            print('Bundling..')
        self.bundle = [self.train, self.test]

    def categoricals(self, categories, bundle, target):
        """
        creates a bunch of categorical encodings using the method learnt from the kaggle feature
        engineering class- Count encodings are also things to consider adding in the near future.
        """
        target_enc = ce.CatBoostEncoder(cols=categories)
        target_enc.fit(self.bundle[0][categories], self.bundle[0][target])
        train_ = self.bundle[0].join(self.bundle[0].transform(self.bundle[0][categories]).add_suffix('_cb'))
        test_ = self.bundle[1].join(target_enc.transform(self.bundle[1][categories]).add_suffix('_cb'))
        return train_, test_

    def add_interactions(self, numerical=True, categories=False):
        """
        generate mathematical feature interactions on numerical columns.
        multiplying, dividing and applying the crabby formula.

        also generate categorical features by combining existing categorical features
        using concatenation
        """
        if numerical:
            numbs = [column for column in self.data.select_dtypes('number') if len(self.data[column].unique()) > 10]
            cardinal = 0
            for column in numbs:
                for index in range(cardinal, len(numbs)):
                    if index != numbs.index(column):
                        self.data['Multiple{}-{}-{}'.format(index, column, numbs[index])] = self.data[column] * \
                                                                                            self.data[numbs[index]]
                        self.data['Ratio{}-{}-{}'.format(index, column, numbs[index])] = self.data[column] / self.data[
                            numbs[index]]
                        self.data['Crabby{}-{}-{}'.format(index, column, numbs[index])] = (
                                (self.data[column] + self.data[numbs[index]]) / (self.data[numbs[index]] ** 2))
                    else:
                        pass
                cardinal = cardinal + 1
            cardinal = 0

        if categories:
            numbs = [column for column in self.data.select_dtypes('object').columns]
            for column in numbs:
                for index in range(cardinal, len(numbs)):
                    if index != numbs.index(column):
                        self.data['{}-{}-{}'.format(index, column, numbs[index])] = self.data[column] + '_' + self.data[
                            numbs[index]]
                    else:
                        pass
                cardinal = cardinal + 1

    def viewmissing(self, heat=False):
        if heat == False:
            mis_val = self.data.isnull().sum()
            mis_val_percent = 100 * self.data.isnull().sum() / len(self.data)
            mis_val_table = pd.concat([mis_val, mis_val_percent], axis=1)
            mis_val_table_ren_columns = mis_val_table.rename(
                columns={0: 'Missing Values', 1: '% of Total Values'})
            mis_val_table_ren_columns = mis_val_table_ren_columns[
                mis_val_table_ren_columns.iloc[:, 1] != 0].sort_values(
                '% of Total Values', ascending=False).round(1)
            if len(mis_val_table_ren_columns) > 1:
                print("Your selected dataframe has " + str(self.data.shape[1]) + " columns.\n"
                                                                                 "There are " + str(
                    mis_val_table_ren_columns.shape[0]) +
                      " columns that have missing values.")
            else:
                print("No missing Values!")
            return mis_val_table_ren_columns
        elif heat:
            sb.heatmap(self.data.isnull(), cbar=False)
        else:
            print('Error 404! Lol, you set the heat wrongly though!')

    def hour_split(self, hour):
        self.data['hours {}'.format(hour)] = 0
        self.data.loc[self.data[hour] < 12, 'hours {}'.format(hour)] = 'morning'
        self.data.loc[(self.data[hour] >= 12) & (self.data[hour] < 16), 'hours {}'.format(hour)] = 'afternoon'
        self.data.loc[(self.data[hour] >= 16) & (self.data[hour] < 20), 'hours {}'.format(hour)] = 'evening'
        self.data.loc[(self.data[hour] >= 19) & (self.data[hour] <= 24), 'hours {}'.format(hour)] = 'night'

    def date_split(self, date):
        a = pd.to_datetime(self.data[date])
        self.data['weekday'] = a.dt.dayofweek
        self.data['hour'] = a.dt.hour
        self.data['year'] = a.dt.dayofyear
        self.data['day'] = a.dt.day
        self.data['quarter'] = a.dt.quarter
        self.data['is_weekend'] = 0
        self.data['is_monthend'] = 0
        self.data['is_monthstart'] = 0
        self.data.loc[(self.data['day'] >= 26), 'is_monthend'] = 1
        self.data.loc[(self.data['day'] <= 5), 'is_monthstart'] = 1
        self.data.loc[(self.data['weekday'] >= 4), 'is_weekend'] = 1

    def catcode(self, column, encoded=False):
        if encoded == False:
            self.data[column] = self.data[column].astype('category')
            self.data[column] = self.data[column].cat.codes
        else:
            self.encoded_data[column] = self.encoded_data[column].astype('category')
            self.encoded_data[column] = self.encoded_data[column].cat.codes
        return 'done'

    def quality_report(self):
        dtypes = self.data.dtypes
        nuniq = self.data.T.apply(lambda x: x.nunique(), axis=1)
        total = self.data.isnull().sum().sort_values(ascending=False)
        percent = (self.data.isnull().sum() / self.data.isnull().count() * 100).sort_values(ascending=False)
        quality_df = pd.concat([total, percent, nuniq, dtypes], axis=1, keys=['Total', 'Percent', 'Nunique', 'Dtype'])
        display(quality_df)

    def eda(self, target):
        for col in self.data.drop(target, axis=1).columns:
            if self.data[col].dtype == 'object' or self.data[col].nunique():
                xx = self.data.groupby(col)[target].value_counts().unstack(1)
                per_not_promoted = xx.iloc[:, 0] * 100 / xx.apply(lambda x: x.sum(), axis=1)
                per_promoted = xx.iloc[:, 1] * 100 / xx.apply(lambda x: x.sum(), axis=1)
                xx['%_0'] = per_not_promoted
                xx['%_1'] = per_promoted
                display(xx)

    def drop(self, column):
        recycle[column] = self.data[column].copy()
        self.data.drop(columns=column, inplace=True)

    def pick(self, column):
        self.data[column] = recycle[column]

    def evaluate(self, target, model, test_size=.25, stratify=True, metric=accuracy_score):
        if stratify:
            x_train, x_test, y_train, y_test = train_test_split(self.data.drop(target, axis=1), self.data[target],
                                                                stratify=self.data[target], test_size=test_size)
            model.fit(x_train, y_train)
            pred = model.predict(x_test)
            metric(pred, y_test)
        else:
            x_train, x_test, y_train, y_test = train_test_split(self.data.drop(target, axis=1), self.data[target],
                                                                test_size=self.test_size)
            model.fit(x_train, y_train)
            pred = model.predict(x_test)
            metric(pred, y_test)
        return pred


class Utility:

    def __init__(self):
        self.nothing = None

    def update_progress(self, index, range_of_index):
        progress = index / range_of_index
        bar_length = 40
        if isinstance(progress, int):
            progress = float(progress)
        if not isinstance(progress, float):
            progress = 0
        if progress < 0:
            progress = 0
        if progress >= 1:
            progress = 1
        block = int(round(bar_length * progress))
        clear_output(wait=True)
        text = "Progress: [{0}] {1:.1f}%".format("#" * block + '>>' + "_" * (bar_length - block), progress * 100)
        one_of = "Processing {} of {}".format(index + 1, range_of_index + 1)
        print(text)
        print(one_of)
        if index == range_of_index:
            print('Processing completed')

    def generate_submission(self, submission_file, target, predicted_values):
        submission_file[target] = predicted_values
        submission_file.to_csv(input('Enter filename: ') + '.csv', index=False)
        print('Submission File has been created, Goodluck!')


class Imbalanced:

    def __init__(self, data):
        self.data = data

    def DivideAndConquer(self, target, minority_class, majority_class, n=5000):
        total = len(self.data)
        minority = self.data[self.data[target] == minority_class]
        majority = self.data[self.data[target] == majority_class]
        majoritysampling = majority.sample(n=len(majority), random_state=10)
        new_majority_len = ((len(majority) - len(minority)) / total) * n
        iterations = len(majority) / new_majority_len
        pickrange = list(range(int(new_majority_len), len(majority), int(new_majority_len)))
        print(len(pickrange))
        iterable = [0]
        datatable = []

        for IndexValue in range(int(iterations)):
            newMajority = majoritysampling[iterable[-1]:pickrange[IndexValue]]
            new_data = pd.concat([newmajority, minority], ignore_index=True)
            datatable.append(new_data)
            iterable.append(pickrange[IndexValue])
            utility.update_progress(IndexValue, int(iterations) - 1)
        return datatable


class Visual:

    def __init__(self):
        self.data = pd.DataFrame()
        self.column = ['dummy']
        self.target = None
        self.size = [20, 20]

    def adjust(self):
        self.column.insert(0, 'dummy')

    def setsize(self):
        sns.set(rc={'figure.figsize': (self.size[0], self.size[1])}, font_scale=1.5, style='darkgrid')

    def count(self):
        for index in range(len(self.column)):
            if index == 0:
                index += 1
            plt.subplot(round(len(self.column) / 2), 2, index)
            sns.countplot(self.data[self.column[index]], hue=self.data[self.target])


class MultiColumnLabelEncoder:
    """
    Parameters
    ----------
    columns : array-like

    Examples
    --------
    dsa_2019 = {'Names': ['Obinna', 'Adeola', 'Hakeem'], 'Gender': ['Male', 'Female', 'Male']}
    dsa_df = pd.DataFrame(data = dsa_2019)
    dsa_df

     	Names 	Gender
    0 	Obinna 	Male
    1 	Adeola 	Female
    2 	Hakeem 	Male

    enc = MultiColumnLabelEncoder(columns=['Gender'])
    enc.fit_transform(dsa_df)

     	Names 	Gender
    0 	Obinna 	1
    1 	Adeola 	0
    2 	Hakeem 	1

    """

    def __init__(self, columns=None):
        # list of column to encode    
        self.columns = columns

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        """
        Transforms columns of X specified in self.columns using
        LabelEncoder(). If no columns specified, transforms all
        columns in X.

        """

        X_copy = X.copy()

        if self.columns is not None:
            for column in self.columns:
                X_copy[column] = LabelEncoder().fit_transform(X_copy[column])
        else:
            for colname, column in X_copy.iteritems():
                X_copy[colname] = LabelEncoder().fit_transform(column)

        return X_copy

    def fit_transform(self, X, y=None):
        return self.fit(X, y).transform(X)


class Add_interactions:
    """
    Parameters
    ----------
    columns : array-like

    Examples
    --------
    dsa_2019 = {'Names': ['Obinna', 'Adeola', 'Hakeem'], 'Gender': ['Male', 'Female', 'Male'],
           'Height': [23, 45, 67], 'State':['Abia', 'Ogun', "Ogun"]}
    dsa_df = pd.DataFrame(data = dsa_2019)
    dsa_df

     	Names 	Gender 	Height 	State
    0 	Obinna 	Male 	23 	Abia
    1 	Adeola 	Female 	45 	Ogun
    2 	Hakeem 	Male 	67 	Ogun


    If Column = None i.e No column is specified
    interact = Add_interactions()
    interact.fit_transform(dsa_df)

 	       Names 	Gender 	Height 	State 	Names_Gender 	Names_Height 	Names_State 	Gender_Height 	Gender_State 	Height_State
    0 	    2.0 	 1.0 	 0.0 	 0.0 	   2.0 	         0.0 	            0.0 	       0.0 	          0.0 	            0.0
    1 	    0.0 	 0.0 	 1.0 	 1.0 	   0.0 	         0.0 	            0.0 	       0.0 	          0.0 	            1.0
    2 	    1.0 	 1.0 	 2.0 	 1.0 	   1.0 	         2.0 	            1.0 	       2.0 	          1.0 	            2.0

    If Column = ['Names', 'Gender', 'State']
    interact = Add_interactions(columns=Column)
    interact.fit_transform(dsa_df)

     	Names 	Gender 	Height 	State 	Names_Gender 	Names_State 	Gender_State
    0 	  2 	  1 	 23 	  0 	    2.0 	       0.0 	         0.0
    1 	  0 	  0 	 45 	  1 	    0.0 	       0.0 	         0.0
    2 	  1 	  1 	 67 	  1 	    1.0 	       1.0 	         1.0


    """

    def __init__(self, columns=None):
        # Columns to interact   
        self.columns = columns

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        """
        Transforms

        """

        X_copy = X.copy()
        enc = MultiColumnLabelEncoder(columns=self.columns)
        X_copy_enc = enc.fit_transform(X_copy)
        poly = PolynomialFeatures(interaction_only=True, include_bias=False)

        if self.columns is not None:
            column_combos = list(combinations(list(self.columns), 2))
            X_columns = X_copy_enc.loc[:, self.columns]
            new_col = list(X_columns.columns)
            colnames = new_col + ['_'.join(x) for x in column_combos]

            df_new = poly.fit_transform(X_columns)
            dd = pd.DataFrame(df_new, columns=colnames)
            data = pd.concat([X_copy_enc, dd], axis=1)
            data = data.loc[:, ~data.columns.duplicated()]

        else:
            column_combos = list(combinations(list(X_copy.columns), 2))
            colnames = list(X_copy.columns) + ['_'.join(x) for x in column_combos]
            df_new = poly.fit_transform(X_copy_enc)

            data = pd.DataFrame(df_new, columns=colnames)

        return data

    def fit_transform(self, X, y=None):
        return self.fit(X, y).transform(X)
