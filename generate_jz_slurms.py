models = {
    #local models
    "/gpfswork/rech/lak/utb11pp/models/mistralai/Mistral-7B-v0.1" : "mistral",
    "/gpfswork/rech/lak/utb11pp/models/lmsys/vicuna-7b-v1.5" : "vic7",
    "/gpfswork/rech/lak/utb11pp/models/lmsys/vicuna-13b-v1.5" : "vic13",
    #common models
    "/gpfsdswork/dataset/HuggingFace_Models/bigscience/bloom-7b1": "bloom7",
    "/gpfsdswork/dataset/HuggingFace_Models/bigscience/bloomz-7b1": "bloomz7",
    "/gpfsdswork/dataset/HuggingFace_Models/bigscience/bloom" : "bloombig",
    "/gpfsdswork/dataset/HuggingFace_Models/bigscience/bloomz" : "bloomzbig",
    "/gpfsdswork/dataset/HuggingFace_Models/tiiuae/falcon-7b": "falcon7",
    "/gpfsdswork/dataset/HuggingFace_Models/tiiuae/falcon-40b": "falcon40",
    "/gpfsdswork/dataset/HuggingFace_Models/bofenghuang/vigogne-2-13b-instruct/": "vigogne13",
}
datasets = {
    #local datasets
    "/gpfswork/rech/lak/utb11pp/data/conll2003": "conll2003",
    "/gpfswork/rech/lak/utb11pp/data/emea": "emea",
    "/gpfswork/rech/lak/utb11pp/data/medline": "medline",
    "/gpfswork/rech/lak/utb11pp/data/n2c2": "n2c2",
    "/gpfswork/rech/lak/utb11pp/data/mnaguib/WikiNER/en": "wnen",
    "/gpfswork/rech/lak/utb11pp/data/mnaguib/WikiNER/fr": "wnfr",
    "/gpfswork/rech/lak/utb11pp/data/mnaguib/WikiNER/es": "wnes",
}
fixed_header="""#!/bin/bash

#SBATCH --job-name={model_short_name}_{dataset_short_name}
#SBATCH --output={model_short_name}_{dataset_short_name}.out
#SBATCH --error={model_short_name}_{dataset_short_name}.out
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=20
#SBATCH --time=20:00:00
#SBATCH --gres=gpu:2
#SBATCH --account=lak@a100
#SBATCH -C a100


module purge
module load llm

python3 $WORK/autoregressive_ner/clm_experiment.py --model_name {model} --dataset_name {dataset}  --n_gpus 2 -d"""

def generate_slurm(model, dataset):
    model_short_name = models[model]
    dataset_short_name = datasets[dataset]
    with open(f"slurms_jz/{model_short_name}_{dataset_short_name}.slurm", "w") as f:
        f.write(fixed_header.format(model_short_name=model_short_name, dataset_short_name=dataset_short_name, model=model, dataset=dataset))

for model in models:
    for dataset in datasets:
        generate_slurm(model, dataset)