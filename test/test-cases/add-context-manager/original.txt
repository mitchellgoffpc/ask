#!/usr/bin/env python
import os
import time
import types
import torch
import argparse
import requests
import tiktoken
import safetensors
from pathlib import Path
from tqdm import tqdm, trange
from tiktoken.load import load_tiktoken_bpe
from models.gpt import GPT, GPTConfig
from models.llama import Llama, LlamaConfig

CHECKPOINT_DIR = Path(__file__).parent / 'pretrained'
HUGGINGFACE_API_KEY = os.getenv('HUGGINGFACE_API_KEY')
GPT2_URL = "https://huggingface.co/{model}/resolve/main/model.safetensors"
LLAMA3_URL = "https://huggingface.co/meta-llama/Meta-Llama-3-{size}/resolve/main/model-{index:05d}-of-00004.safetensors"
LLAMA3_TOKENIZER_URL = 'https://huggingface.co/meta-llama/Meta-Llama-3-8B/resolve/main/original/tokenizer.model'

CONFIGS = {
    'gpt2': GPTConfig(num_layers=12, num_heads=12, embed_size=768),
    'gpt2-medium': GPTConfig(num_layers=24, num_heads=16, embed_size=1024),
    'gpt2-large': GPTConfig(num_layers=36, num_heads=20, embed_size=1280),
    'gpt2-xl': GPTConfig(num_layers=48, num_heads=25, embed_size=1600),
    'llama3-8b': LlamaConfig(num_layers=32, num_heads=32, embed_size=4096)}


def load_file(url, output_fn):
    tmp_output_fn = f'{output_fn}.tmp'
    if not os.path.exists(output_fn):
        headers = {'Authorization': f'Bearer {HUGGINGFACE_API_KEY}'} if HUGGINGFACE_API_KEY else {}
        r = requests.get(url, headers=headers, stream=True)
        r.raise_for_status()
        file_size = int(r.headers['content-length'])
        chunk_size = 128 * 1000
        with open(tmp_output_fn, 'wb') as f:
            with tqdm(desc="Fetching " + url, total=file_size, unit_scale=True) as pbar:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
                    pbar.update(chunk_size)
        os.rename(tmp_output_fn, output_fn)

def load_checkpoint(weights_url, checkpoint_fn):
    load_file(weights_url, checkpoint_fn)
    with safetensors.safe_open(checkpoint_fn, framework='pt') as f:
        return {k: f.get_tensor(k) for k in f.keys()}

def load_checkpoints(weights_urls, checkpoint_fns):
    state_dict = {}
    for weights_url, checkpoint_fns in zip(weights_urls, checkpoint_fns):
        state_dict.update(load_checkpoint(weights_url, checkpoint_fns))
    return state_dict

def load_llama_tokenizer(model_url, model_fn):
    load_file(model_url, model_fn)
    mergeable_ranks = load_tiktoken_bpe(str(model_fn))
    num_base_tokens = len(mergeable_ranks)
    num_reserved_special_tokens = 256
    pat_str = r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}{1,3}| ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"
    special_tokens = [
        "<|begin_of_text|>",
        "<|end_of_text|>",
        "<|reserved_special_token_0|>",
        "<|reserved_special_token_1|>",
        "<|reserved_special_token_2|>",
        "<|reserved_special_token_3|>",
        "<|start_header_id|>",
        "<|end_header_id|>",
        "<|reserved_special_token_4|>",
        "<|eot_id|>",  # end of turn
    ] + [
        f"<|reserved_special_token_{i}|>"
        for i in range(5, num_reserved_special_tokens - 5)
    ]
    special_tokens = {token: num_base_tokens + i for i, token in enumerate(special_tokens)}
    tokenizer = tiktoken.Encoding(
        name=model_fn.name,
        pat_str=pat_str,
        mergeable_ranks=mergeable_ranks,
        special_tokens=special_tokens,
    )
    def encode(text: str): return [tokenizer._special_tokens['<|begin_of_text|>'], *tokenizer.encode(text)]
    def decode(tokens: str): return tokenizer.decode(tokens[1:])  # remove begin_of_text token
    return types.SimpleNamespace(encode=encode, decode=decode)


def fix_gpt_state_dict(state_dict):
    replacements = {
        'h.': 'blocks.',
        'wte.': 'embed_tokens.',
        'wpe.': 'embed_pos.',
        'attn.c_attn': 'attn.qkv',
        'attn.c_proj': 'attn.proj',
        'mlp.c_fc': 'mlp.fc1',
        'mlp.c_proj': 'mlp.fc2',
        'ln_1.': 'ln1.',
        'ln_2.': 'ln2.',
        'ln_f.': 'ln.'}
    linears = ['attn.qkv.weight', 'attn.proj.weight', 'mlp.fc1.weight', 'mlp.fc2.weight']
    biases = ['attn.bias', 'attn.masked_bias']

    for src, dst in replacements.items():
        state_dict = {k.replace(src, dst): v for k,v in state_dict.items()}
    state_dict = {k:v for k,v in state_dict.items() if not any(x in k for x in biases)}
    state_dict = {k: v.transpose(-1, -2) if any(x in k for x in linears) else v for k,v in state_dict.items()}
    state_dict['fc_out.weight'] = state_dict['embed_tokens.weight']
    return state_dict

def fix_llama_state_dict(state_dict):
    replacements = {
        'model.': '',
        'layers.': 'blocks.',
        'input_layernorm': 'ln1',
        'post_attention_layernorm': 'ln2',
        'self_attn.': 'attn.',
        'attn.o_proj.': 'attn.out_proj.',
        'mlp.': 'ff.',
        'norm.': 'ln.',
        'lm_head.': 'out_proj.'}
    for src, dst in replacements.items():
        state_dict = {k.replace(src, dst): v for k,v in state_dict.items()}
    return state_dict


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GPT model generator')
    parser.add_argument('model', choices=CONFIGS.keys(), help='Model configuration to use')
    parser.add_argument('-f', '--file', help='Path to the checkpoint file to load')
    parser.add_argument('-b', '--benchmark', action='store_true', help='Run a benchmark')
    parser.add_argument('-p', '--prompt', help='Prompt to generate completion for')
    args = parser.parse_args()

    st = time.time()
    config = CONFIGS[args.model]
    device = torch.device('cuda')

    # Load the checkpoint
    if args.file:
        with safetensors.safe_open(args.file, framework="pt", device="cpu") as f:
            state_dict = {k: f.get_tensor(k) for k in f.keys()}
    elif args.model.startswith('gpt2'):
        checkpoint_fn = CHECKPOINT_DIR / f'{args.model}.safetensors'
        weights_url = GPT2_URL.format(model=args.model)
        state_dict = load_checkpoint(weights_url, checkpoint_fn)
        state_dict = fix_gpt_state_dict(state_dict)
    elif args.model.startswith('llama3'):
        assert HUGGINGFACE_API_KEY, "HUGGINGFACE_API_KEY must be set to download llama models"
        weights_urls = [LLAMA3_URL.format(size=args.model.removeprefix('llama3-'), index=i) for i in range(1, 5)]
        checkpoint_fns = [CHECKPOINT_DIR / f'{args.model}-{i:05d}.safetensors' for i in range(len(weights_urls))]
        state_dict = load_checkpoints(weights_urls, checkpoint_fns)
        state_dict = fix_llama_state_dict(state_dict)

    # Create the model
    if isinstance(config, GPTConfig):
        tokenizer = tiktoken.get_encoding("gpt2")
        model = GPT(config).to(device)
    else:
        torch.set_default_dtype(torch.bfloat16)
        torch.set_default_device(device)
        tokenizer = load_llama_tokenizer(LLAMA3_TOKENIZER_URL, CHECKPOINT_DIR / 'llama-tokenizer.model')
        model = Llama(config)

    model.eval().load_state_dict(state_dict)
    print(f"Loaded model in {time.time() - st:.2f}s")

    # Benchmark
    if args.benchmark:
        large_context = torch.randint(0, 50257, size=(1, 1024)).to(device)
        with torch.no_grad():
            for i in trange(1024, desc="benchmarking bs=1, seqlen=1"):
                data = model(large_context[:,i:i+1])

    # Decode
    else:
        prompt = args.prompt or "The capital of Germany is Berlin. The capital of France is"
        tokens = tokenizer.encode(prompt)
        context = torch.tensor(tokens)[None].to(device)
        result = model.generate(context, num_tokens=3, top_k=10)
        print(f"Prompt:    ", prompt)
        print(f"Completion:", tokenizer.decode(result[0].tolist()))
