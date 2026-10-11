"""Bounded inference adapters for isolated comparative experiments."""
import json
import urllib.request

from request_budget import remaining


def complete(url, backend, model, messages, schema, options):
    if backend == "ollama":
        endpoint = "/api/chat"
        payload = {"model": model, "messages": messages, "stream": False,
                   "think": False, "format": schema, "options": options}
    elif backend == "llamacpp":
        endpoint = "/v1/chat/completions"
        payload = {"model": model, "messages": messages, "stream": False,
                   "temperature": options["temperature"], "seed": options["seed"],
                   "max_tokens": options["num_predict"],
                   "chat_template_kwargs": {"enable_thinking": False},
                   "response_format": {"type": "json_schema", "json_schema": {
                       "name": "cas_experiment", "strict": True, "schema": schema}}}
    else:
        raise ValueError("unknown experimental inference backend")
    request = urllib.request.Request(url + endpoint, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=remaining(120)) as stream:
        result = json.load(stream)
    if backend == "ollama":
        content = result["message"]["content"]
        tokens = {"prompt_tokens": result.get("prompt_eval_count"), "output_tokens": result.get("eval_count")}
    else:
        content = result["choices"][0]["message"]["content"]
        tokens = {"prompt_tokens": result.get("usage", {}).get("prompt_tokens"),
                  "output_tokens": result.get("usage", {}).get("completion_tokens")}
    return content, tokens
