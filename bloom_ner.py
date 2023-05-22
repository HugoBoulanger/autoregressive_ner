import re
import datasets
import requests
# from huggingface_hub import HfApi
from sklearn.metrics import f1_score, precision_score, recall_score

def example2string(example, ner_tag_id, begin_tag='@@', end_tag='##'):
    # if ner_tag_id = 3 and 3 stands for LOC, beginning tag = @@ and ending tag = ##
    # and the example is {'id': 0, 'words': ['I', 'love', 'Paris', 'and', 'Berlin'], 'ner_tags': [0, 0, 3, 0, 3]}
    # the returned string will be 'I love @@Paris## and @@Berlin##'
    words = example['words']
    ner_tags = example['ner_tags']
    # initialize the string
    string = ''
    for i, (word, ner_tag) in enumerate(zip(words, ner_tags)):
        # if the ner tag is equal to the given ner tag id and the last ner tag was not equal to the given ner tag id
        if ner_tag == ner_tag_id and (ner_tags[i-1] != ner_tag_id if i > 0 else True):
            # add the beginning tag to the string
            string += begin_tag
        # add the word to the string
        string += word
        # if the ner tag is equal to the given ner tag id and the next ner tag is not equal to the given ner tag id
        if ner_tag == ner_tag_id and (ner_tags[i+1] != ner_tag_id if i < len(ner_tags)-1 else True):
            # add the ending tag to the string
            string += end_tag
        # add a space to the string
        string += ' '
    # return the string
    return string.strip()


def DISO_prompt(example, begin_tag='@@', end_tag='##'):
    #this function takes an example and a ner tag and returns a prompt
    prompt = "Je suis un clinicien expert, je sais identifier les mentions des maladies et des symptômes dans une phrase. Je peux aussi les mettre en forme. Voici quelques exemples de phrases que je peux traiter :\n"
    prompt+= "Entrée : Diagnostic et traitement de l' impuissance . Indications des injections intracaverneuses .\n"
    prompt+= "Sortie : Diagnostic et traitement de l' {0}impuissance{1} . Indications des injections intracaverneuses .\n".format(begin_tag, end_tag)
    prompt+= "Entrée : Stratégie chirurgicale de l' adénocarcinome du cardia .\n"
    prompt+= "Sortie : Stratégie chirurgicale de l' {0}adénocarcinome du cardia{1} .\n".format(begin_tag, end_tag)
    prompt+= "Entrée : Le paracétamol dans le traitement des douleurs arthrosiques .\n"
    prompt+= "Sortie : Le paracétamol dans le traitement des {0}douleurs arthrosiques{1} .\n".format(begin_tag, end_tag)
    prompt+= "Imite-moi. Identifie les mentions de maladies ou de symptômes dans la phrase suivante, en mettant \"{0}\" devant et un \"{1}\" derrière la mention.\n".format(begin_tag, end_tag)
    prompt+= "Entrée : "+example+"\n"
    prompt+= "Sortie : "
    return prompt

def PER_prompt(example, begin_tag='@@', end_tag='##'):
    #this function takes an example and a ner tag and returns a prompt
    prompt = "Je suis un linguiste expert, je sais identifier les mentions des personnes dans une phrase. Je peux aussi les mettre en forme. Voici quelques exemples de phrases que je peux traiter :\n"
    prompt+= "Entrée : Le président de la République française est Emmanuel Macron .\n"
    prompt+= "Sortie : Le président de la République française est {0}Emmanuel Macron{1} .\n".format(begin_tag, end_tag)
    prompt+= "Entrée : Barack Obama est le président des États-Unis .\n"
    prompt+= "Sortie : {0}Barack Obama{1} est le président des États-Unis .\n".format(begin_tag, end_tag)
    prompt+= "Entrée : Paris est la capitale de la France .\n"
    prompt+= "Sortie : Paris est la capitale de la France .\n"
    prompt+= "Entrée : Zinedine Zidane explique que le Real Madrid a besoin de Karim Benzema .\n"
    prompt+= "Sortie : {0}Zinedine Zidane{1} explique que le Real Madrid a besoin de {0}Karim Benzema{1} .\n".format(begin_tag, end_tag)
    prompt+= "Imite-moi. Identifie les mentions de personnes dans la phrase suivante, en mettant \"{0}\" devant et un \"{1}\" derrière la mention dans la phrase suivante.\n".format(begin_tag, end_tag)
    prompt+= "Entrée : "+example+"\n"
    prompt+= "Sortie : "
    return prompt

def get_bloom_predictions(example_string, ner_tag):
    API_URL = "https://api-inference.huggingface.co/models/bigscience/bloom"
    headers = {"Authorization": "Bearer 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"}
    
    def query(payload):
        response = requests.post(API_URL, headers=headers, json=payload)
        return response.json()
        
    if ner_tag == 'DISO':
        prompt = DISO_prompt(example_string)
    elif ner_tag == 'PER':
        prompt = PER_prompt(example_string)
    else:
        raise NotImplementedError

    output = query({
        "inputs": prompt, "options": {"use_cache": True},
        "parameters": {"max_new_tokens": 100,"return_full_text": False,"top_p": 0.9,"top_k": 3,"temperature": 0.7,},
    })
    if "error" in output:
        raise Exception(output['error'])
    return output[0]['generated_text'].split('\n')[0]
     
def evaluate_bloom_prediction(example, ner_tag, ner_tag_id):
    #example is a dictionary with the keys 'doc_id', 'words', 'ner_tags'
    words = example['words'] if 'words' in example else example['tokens']
    ner_tags = example['ner_tags']
    target = example2string({'words': words, 'ner_tags': ner_tags}, ner_tag_id)
    bloom_prediction = get_bloom_predictions(' '.join(words), ner_tag)
    print(bloom_prediction)
    

# dataset = datasets.load_dataset('meczifho/quaero')
dataset = datasets.load_dataset('Jean-Baptiste/wikiner_fr')
examples = dataset['train']

for i in range(10, 20):
    # evaluate_bloom_prediction(examples[i], 'DISO', 3)
    evaluate_bloom_prediction(examples[i], 'PER', 2)