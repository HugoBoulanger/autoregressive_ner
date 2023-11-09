import datetime
import os
import argparse
import logging
import random
import json
from vllm import LLM
import torch

from clm_predict import predict_for_dataset, MODEL_INSTRUCTION_TEMPLATES
from nlstruct import BRATDataset, HuggingfaceNERDataset
from nlstruct.metrics import MetricsCollection, DocumentEntityMetric
from nlstruct.data_utils import sentencize
from dataset_info import get_dataset_colnames, get_dataset_ner_tags, get_dataset_tag_map, get_dataset_language
from pred_utils import full_preds_string, get_metrics_string

args = argparse.ArgumentParser()
args.add_argument("--dataset_name", type=str, help="dataset name")
args.add_argument('-d', "--load_dataset_from_disk", action="store_true")

#ABLATION ARGS
args.add_argument('--random_seed', type=int, default=42)
args.add_argument('--partition_seed', type=int, default=1)
args.add_argument("--begin_tag", type=str, default="@@")
args.add_argument("--end_tag", type=str, default="##")
args.add_argument("--n_few_shot", type=int, default=5)
args.add_argument("--criterion", type=str, default="most_occurences")
args.add_argument('--prompt_language', type=str, default="en")
args.add_argument('--prompt_subjective', type=str)
args.add_argument('--prompt_ner_tag_source', type=str, default="standard")
args.add_argument('--prompt_ask', action="store_true")
args.add_argument('--prompt_long_answer', action="store_true")
args.add_argument('--prompt_dash', action="store_true")
args.add_argument('-n', '--n_gpus', type=int, default=1)
args.add_argument('-s', '--training_size', type=int, default=100)
args.add_argument('-t', '--test_on_test_set', action="store_true")
args.add_argument('--do_sample', action="store_true")
args.add_argument('--no_write_log', dest='write_log', action='store_false')
args.add_argument('--no_control', dest='control', action='store_false')
args.add_argument('--no_self_verification', dest='self_verification', action='store_false')
args = args.parse_args()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("experiment")

random.seed(args.random_seed)

try :
    doc_id_colname, words_colname, ner_tags_colname = get_dataset_colnames(args.dataset_name)
    dataset = HuggingfaceNERDataset(
        dataset_name=args.dataset_name,
        tag_map=get_dataset_tag_map(args.dataset_name),
        doc_id_colname=doc_id_colname,
        words_colname=words_colname,
        ner_tags_colname=ner_tags_colname,
        load_from_disk=args.load_dataset_from_disk,
    )
    #This is not supposed to be here, but WikiNER is a mess for now and I have no time to fix it
    if args.dataset_name.endswith("WikiNER/en"):
        dataset.train_data = [e for e in dataset.train_data if e['doc_id'].startswith('en')]
    elif args.dataset_name.endswith("WikiNER/fr"):
        dataset.train_data = [e for e in dataset.train_data if e['doc_id'].startswith('fr')]
    elif args.dataset_name.endswith("WikiNER/es"):
        dataset.train_data = [e for e in dataset.train_data if e['doc_id'].startswith('es')]
except:
    dataset = BRATDataset(
        train= f"{args.dataset_name}/train",
        val= 0, 
        test= f"{args.dataset_name}/test",
    )

traindev_dataset = []
for e in dataset.train_data:
    sentences = sentencize(e, reg_split=r"(?<=[.|\s])(?:\s+)(?=[A-Z])", entity_overlap="split")
    traindev_dataset.extend([s for s in sentences if len(s['text']) < 512])
test_dataset = []
for e in dataset.test_data:
    sentences = sentencize(e, reg_split=r"(?<=[.|\s])(?:\s+)(?=[A-Z])", entity_overlap="split")
    test_dataset.extend([s for s in sentences if len(s['text']) < 512])
traindev_dataset_this_seed = random.Random(args.partition_seed).sample(traindev_dataset, args.training_size)

ner_tags = get_dataset_ner_tags(args.dataset_name)
language = get_dataset_language(args.dataset_name)

metrics = MetricsCollection({
    "exact": DocumentEntityMetric(binarize_tag_threshold=1., binarize_label_threshold=1., add_label_specific_metrics=ner_tags, filter_entities=ner_tags),
    "partial": DocumentEntityMetric(binarize_tag_threshold=1e-5, binarize_label_threshold=1., add_label_specific_metrics=ner_tags, filter_entities=ner_tags),
})

################# MODEL LOADING #################
compute_capability = torch.cuda.get_device_capability()
llm = LLM(args.model_name, tensor_parallel_size=args.n_gpus, seed=args.random_seed, dtype="float16" if compute_capability[0]<8 else "auto", trust_remote_code=True)

################# EXPERIMENT #################
folder_name = 'results'
script_dir = os.path.dirname(__file__)
os.makedirs(os.path.join(script_dir, folder_name), exist_ok=True)
res_dict = {}
time_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
last_two_dirs = '-'.join(args.dataset_name.split('/')[-2:])
model_base_name = os.path.basename(args.model_name)

res_dict['dataset_name'] = last_two_dirs
res_dict['begin_tag'] = args.begin_tag
res_dict['end_tag'] = args.end_tag
res_dict['n_few_shot'] = args.n_few_shot
res_dict['model_name'] = args.model_name
res_dict['criterion'] = args.criterion
res_dict['training_size'] = args.training_size
res_dict['partition_seed'] = args.partition_seed
res_dict['random_seed'] = args.random_seed
res_dict['control'] = args.control
res_dict['self_verification'] = args.self_verification
res_dict['chat_template'] = MODEL_INSTRUCTION_TEMPLATES[args.model_name] if args.model_name in MODEL_INSTRUCTION_TEMPLATES else ""
res_dict['ner_tags'] = ner_tags
res_dict['first_example'] = traindev_dataset_this_seed[0]['text']
res_dict['last_example'] = traindev_dataset_this_seed[-1]['text']
res_dict['test_on_test_set'] = args.test_on_test_set
res_dict['prompt_language'] = args.prompt_language
res_dict['prompt_subjective'] = args.prompt_subjective
res_dict['prompt_ner_tag_source'] = args.prompt_ner_tag_source
res_dict['prompt_ask'] = args.prompt_ask
res_dict['prompt_long_answer'] = args.prompt_long_answer
res_dict['prompt_dash'] = args.prompt_dash

model_kwargs = {
    "num_beams": 3,
    "do_sample": False,
    # "top_p": 0.9,
    # "top_k": 50,
    # "temperature": 0.9,
}
res_dict.update(model_kwargs)

logger.info("Generating...")
textual_outputs, predicted_dataset = predict_for_dataset(
    llm=llm,
    training_data=traindev_dataset_this_seed,
    testing_data=test_dataset if args.test_on_test_set else None,
    ner_tags=ner_tags,
    model_name=args.model_name,
    begin_tag=args.begin_tag,
    end_tag=args.end_tag,
    self_verification=args.self_verification,
    control=args.control,
    n_few_shot=args.n_few_shot,
    criterion=args.criterion,
    model_kwargs=model_kwargs,
    random_seed=args.random_seed,
    prompt_language=args.prompt_language,
    prompt_subjective=args.prompt_subjective,
    prompt_ner_tag_source=args.prompt_ner_tag_source,
    prompt_ask=args.prompt_ask,
    prompt_long_answer=args.prompt_long_answer,
    prompt_dash=args.prompt_dash,
)

logger.info("Evaluating...")
metric_dict = metrics(predicted_dataset, test_dataset if args.test_on_test_set else traindev_dataset_this_seed)
for metric_name, metric_values in metric_dict.items():
    for k,v in metric_values.items():
        if not isinstance(v, int) and not isinstance(v, float):
            metric_dict[metric_name][k] = v.item()
        metric_dict[metric_name][k] = round(metric_dict[metric_name][k], 3)
res_dict.update(metric_dict)
logger.info(get_metrics_string(metric_dict, ner_tags))

if args.write_log:
    full_preds = full_preds_string(textual_outputs, predicted_dataset, test_dataset if args.test_on_test_set else traindev_dataset_this_seed, ner_tags)
    full_preds_path = os.path.join(script_dir, folder_name)+f'/full_preds_{last_two_dirs}_{model_base_name}_{args.random_seed}_{time_str}.txt'
    res_dict['full_preds_path'] = full_preds_path
    with open(full_preds_path, 'w') as f:
        f.write(full_preds)
    res_dict_path = os.path.join(script_dir, folder_name)+f'/res_dict_{last_two_dirs}_{model_base_name}_{args.random_seed}_{time_str}.json'
    with open(res_dict_path, 'w') as f:
        json.dump(res_dict, f)
