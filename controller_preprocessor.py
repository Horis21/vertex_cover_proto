import pandas as pd
from dtcontrol.benchmark_suite import BenchmarkSuite
from dtcontrol.pre_processing.label_pre_processor import LabelPreProcessor
from dtcontrol.pre_processing.maxfreq_pre_processor import MaxFreqPreProcessor
from dtcontrol.pre_processing.norm_pre_processor import NormPreProcessor
from pystreed.binarizer import Binarizer
from genericpath import *
from wakepy import keep
from tqdm import tqdm
import numpy as np

def one_vs_all(df : pd.DataFrame, y):
   datasets = []
   copy = df.copy()
   for label in np.unique(y)[:-1]:
        one_vs_df = copy.copy()
        one_vs_df[0] = (one_vs_df[0] == label).astype(int)

        copy = copy[copy[0] != label]

        datasets.append(one_vs_df)

   return datasets

def check_impossible_split(df : pd.DataFrame):
    feature_vectors = {}
    intersections = {}
    labels = np.unique(y)
    for label in labels:
        feature_vectors[label] = set(tuple(x[1:]) for x in df[df[0] == label].values)

    for i in range(len(labels)):
        for j in range (i+1, len(labels)):

            label1 = labels[i]
            label2 = labels[j]

            feature_vectors1 = feature_vectors[label1]
            feature_vectors2 = feature_vectors[label2]

            intersection = feature_vectors1 & feature_vectors2

            if len(intersection) > 0:
                intersections[(label1,label2)] = intersection 

    return intersections
        

def binarize_df(df):
    x = df.iloc[:, 1:]
    y = df[0]

    min_features_needed = 10000000
    for n_thresholds in tqdm(range(1,2)):
        binarizer = Binarizer("quantile",n_thresholds, None,None)

        binarizer.fit(x,y)
    
        binarized_df = pd.concat([y, pd.DataFrame(binarizer.transform(x))], axis=1)
        
        impossible_splits = check_impossible_split(binarized_df)
        nr_impossible_splits = sum([len(v) for v in impossible_splits.values()])

        max_features_needed = binarized_df.shape[1] - 1 + nr_impossible_splits
        print("max features needed: ", max_features_needed)

        if max_features_needed < min_features_needed or (max_features_needed == min_features_needed and nr_impossible_splits == 0):
            min_features_needed = max_features_needed

            left_to_split = impossible_splits
            best_df = binarized_df
        
        if nr_impossible_splits == 0:
           print("found perfect split with nr of feats: ", min_features_needed)
           break
    
    if len(left_to_split) > 0:
        print("left to split: ", left_to_split)
    
    print("initial nr of features: ", x.shape[1])
    print("final nr of features: ", best_df.shape[1] - 1)
    print("best df: ", best_df)
    return best_df


if __name__ == "__main__":
    loader = BenchmarkSuite()
    preprocessor = MaxFreqPreProcessor()
    loader.add_datasets('controller_examples', include=['aircraft'])

    for ds in loader.datasets:
        print("datsaet called: ", ds.filename)
        ds.load_if_necessary()
       
        preprocssed_dataset = preprocessor.preprocess(ds)
        x = preprocssed_dataset.get_numeric_x()
        y = preprocssed_dataset.get_single_labels()

        x_df = pd.DataFrame(x)

        # Flatten y to ensure it's a 1D array
        y = y.flatten()
        
        # Add labels (y) as the first column
        df = pd.concat([pd.Series(y, name=0), x_df], axis=1)
        
        # Rename feature columns to start from 1
        df.columns = [0] + list(range(1, x_df.shape[1] + 1))
        
        # Reset the index to ensure a sequential index starting from 0
        df.reset_index(drop=True, inplace=True)

        with keep.running():
             binarized_df = binarize_df(df)

        one_vs_all_dfs = one_vs_all(binarized_df, y)

        labels = np.unique(y)[:-1]
        #Save datasets
        for i, dataset in enumerate(one_vs_all_dfs):
            output_csv = 'experiment_datasets/' + ds.filename.split("\\")[1].split(".")[0] + '/' + ds.filename.split("\\")[1].split(".")[0]  + '_' + str(labels[i]) + '_versus_all.csv'
            with open(output_csv, 'w', newline='') as file:
                dataset.to_csv(file, sep=' ', index=False, header=False)