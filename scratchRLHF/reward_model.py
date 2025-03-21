# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/03_reward-model.ipynb.

# %% auto 0
__all__ = ['extract_title', 'extract_abstract', 'get_train_test_split', 'load_data', 'RewardDataset', 'compute_metrics']

# %% ../nbs/03_reward-model.ipynb 2
import pandas as pd, re, numpy as np, joblib, os
from torch.utils.data import Dataset
from transformers import AutoTokenizer, DistilBertForSequenceClassification, TrainingArguments, Trainer

# %% ../nbs/03_reward-model.ipynb 4
def extract_title(content):
    title_matches = re.findall(r'\\title\{(.*?)\}', content, re.DOTALL)
    title = title_matches[0].strip() if title_matches else pd.NA
    return title

def extract_abstract(content):
    abstract_matches = re.findall(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', content, re.DOTALL)
    abstract = abstract_matches[0].strip() if abstract_matches else pd.NA
    return abstract
    

# %% ../nbs/03_reward-model.ipynb 5
def get_train_test_split(X, y, pct=0.8):
    n_data = len(y)
    n_trn = int(n_data * pct)

    rnd_idx = np.random.permutation(n_data)
    trn_idx, tst_idx = rnd_idx[:n_trn], rnd_idx[n_trn:]
    X_trn, y_trn = type(X)({k:v[trn_idx] for k,v in X.items()}), y[trn_idx]
    X_tst, y_tst = type(X)({k:v[tst_idx] for k,v in X.items()}), y[tst_idx]

    return X_trn, y_trn, X_tst, y_tst
    

# %% ../nbs/03_reward-model.ipynb 6
def load_data(pkl_file, x_file, y_file):
    if os.path.exists(pkl_file):
        X, y = joblib.load(pkl_file)
    else:
        X_df = pd.read_csv(x_file, header=None, names=['content'])
        X_df['title'] = X_df['content'].apply(extract_title)
        X_df['abstract'] = X_df['content'].apply(extract_abstract)
    
        tokz = AutoTokenizer.from_pretrained('distilbert-base-uncased')
    
        text = [f'{title} :: {abstract}' for title,abstract in zip(X_df['title'], X_df['abstract'])]
        X = tokz(text, padding="max_length", truncation=True, return_tensors='pt')
    
        y = pd.read_csv(y_file, header=None)
        y = pd.Categorical(y[0], ordered=True, categories=['Reject', 'Accept']).codes
        joblib.dump((X, y), pkl_file)
    return X,y
    

# %% ../nbs/03_reward-model.ipynb 7
class RewardDataset(Dataset):

    def __init__(self, X, y):
        self.X, self.y = X, y

    def __getitem__(self, idx):
        o = {k:v[idx] for k,v in self.X.items()}
        o['labels'] = self.y[idx]
        return o

    def __len__(self):
        return len(self.y)
        

# %% ../nbs/03_reward-model.ipynb 8
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    accuracy = (predictions == labels).mean()
    return {"accuracy": accuracy}
    

# %% ../nbs/03_reward-model.ipynb 20
if __name__ == '__main__':
    data_dir = '/home/scai/phd/aiz218323/scratch/datasets/deepreviewer/'
    output_dir = '/home/scai/phd/aiz218323/scratch/outputs/scratchRLHF/reward_model/'
    pkl_file = '/home/scai/phd/aiz218323/scratch/datasets/processed/scratchRLHF/reward_model.joblib'
    
    x_file = f'{data_dir}/train_papers.csv'
    y_file = f'{data_dir}/train_decision.csv'

    X, y = load_data(x_file, y_file)
    X_trn, y_trn, X_tst, y_tst = get_train_test_split(X, y)

    trn_dataset = RewardDataset(X_trn, y_trn)
    tst_dataset = RewardDataset(X_tst, y_tst)

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=10,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        save_strategy="steps",
        eval_strategy="steps",
        save_steps=500,
        load_best_model_at_end=True,
        metric_for_best_model="accuracy"
    )

    model = DistilBertForSequenceClassification.from_pretrained("distilbert-base-uncased", num_labels=2)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=trn_dataset,
        eval_dataset=tst_dataset,
        compute_metrics=compute_metrics
    )

    trainer.train()

    results = trainer.evaluate()
    print("Evaluation results:", results)
    
