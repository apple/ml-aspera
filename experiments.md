## Replicating experiments

### Complete codebase knowledge (CCK) agent

#### gpt3.5-turbo


```bash
python scripts/agent_runner.py completer.model_name=gpt-3.5-turbo-0125
```

```bash
python scripts/agent_runner.py completer.model_name=gpt-3.5-turbo-0125 completer.seed=1
```

```bash
python scripts/agent_runner.py completer.model_name=gpt-3.5-turbo-0125 completer.seed=2
```

#### gpt4o-mini


```bash
python scripts/agent_runner.py completer.model_name=gpt-4o-mini-2024-07-18
```

```bash
python scripts/agent_runner.py completer.model_name=gpt-4o-mini-2024-07-18 completer.seed=1
```

```bash
python scripts/agent_runner.py completer.model_name=gpt-4o-mini-2024-07-18 completer.seed=2
```

#### gpt4o

```bash
python scripts/agent_runner.py
```

```bash
python scripts/agent_runner.py completer.seed=1
```

```bash
python scripts/agent_runner.py completer.seed=2
```

#### o1-mini

```bash
python scripts/agent_runner.py completer.model_name=o1-mini-2024-09-12 completer.timeout=120
```

```bash
python scripts/agent_runner.py completer.model_name=o1-mini-2024-09-12 completer.timeout=120 completer.seed=1
```

```bash
python scripts/agent_runner.py completer.model_name=o1-mini-2024-09-12 completer.timeout=120 completer.seed=2
```

#### o1

```bash
python scripts/agent_runner.py completer.model_name=o1-preview-2024-09-12 completer.timeout=180
```

```bash
python scripts/agent_runner.py completer.model_name=o1-preview-2024-09-12 completer.timeout=180 completer.seed=1
```

```bash
python scripts/agent_runner.py completer.model_name=o1-preview-2024-09-12 completer.timeout=180 completer.seed=2
```


#### gemini-1.5-pro

```bash
python scripts/agent_runner.py completer=gemini guidelines=gemini_guidelines completer.gcp_project_id={your_gcp_project_id} completer.gcp_location={your_gcp_project_location, e.g.us-central1} --config-name=complete_codebase_knowledge
```

```bash
python scripts/agent_runner.py completer=gemini guidelines=gemini_guidelines completer.seed=1 completer.gcp_project_id={your_gcp_project_id} completer.gcp_location={your_gcp_project_location, e.g.us-central1} --config-name=complete_codebase_knowledge
```

```bash
python scripts/agent_runner.py completer=gemini guidelines=gemini_guidelines completer.seed=2 completer.gcp_project_id={your_gcp_project_id} completer.gcp_location={your_gcp_project_location, e.g.us-central1} --config-name=complete_codebase_knowledge
```

#### gemini-1.0-pro

```bash
python scripts/agent_runner.py completer=gemini completer.model_name=gemini-1.0-pro completer.gcp_project_id={your_gcp_project_id} completer.gcp_location=us-central1 guidelines=gemini_guidelines --config-name=complete_codebase_knowledge
```

```bash
python scripts/agent_runner.py completer=gemini completer.model_name=gemini-1.0-pro completer.seed=1 completer.gcp_project_id={your_gcp_project_id} completer.gcp_location=us-central1 guidelines=gemini_guidelines --config-name=complete_codebase_knowledge
```

```bash
python scripts/agent_runner.py completer=gemini completer.model_name=gemini-1.0-pro completer.seed=2 completer.gcp_project_id={your_gcp_project_id} completer.gcp_location=us-central1 guidelines=gemini_guidelines --config-name=complete_codebase_knowledge
```

### Primitives selection (PS) agent

### o1


```bash
python scripts/agent_runner.py completer.model_name=o1-preview-2024-09-12 completer.timeout=180 --config-name=tool_retrieval
```

```bash
python scripts/agent_runner.py completer.model_name=o1-preview-2024-09-12 completer.seed=1 completer.timeout=180 --config-name=tool_retrieval
```

```bash
python scripts/agent_runner.py completer.model_name=o1-preview-2024-09-12 completer.seed=2 completer.timeout=180 --config-name=tool_retrieval
```

#### gemini-1.5-pro

```bash
python scripts/agent_runner.py completer=gemini guidelines=gemini_guidelines completer.gcp_project_id={your_gcp_project_id} completer.gcp_location={your_gcp_project_location, e.g.us-central1} --config-name=gemini_tool_retrieval
```

```bash
python scripts/agent_runner.py completer=gemini guidelines=gemini_guidelines completer.seed=1 completer.gcp_project_id={your_gcp_project_id} completer.gcp_location={your_gcp_project_location, e.g.us-central1} --config-name=gemini_tool_retrieval
```

```bash
python scripts/agent_runner.py completer=gemini guidelines=gemini_guidelines completer.seed=2 completer.gcp_project_id={your_gcp_project_id} completer.gcp_location={your_gcp_project_location, e.g.us-central1} --config-name=gemini_tool_retrieval
```

To add high-level guidelines to the retrieval prompt:

```bash
python scripts/agent_runner.py completer.model_name=o1-preview-2024-09-12 completer.timeout=180 --config-name=guideline_tool_retrieval
```

```bash
python scripts/agent_runner.py completer.model_name=o1-preview-2024-09-12 completer.seed=1 completer.timeout=180 --config-name=guideline_tool_retrieval
```

```bash
python scripts/agent_runner.py completer.model_name=o1-preview-2024-09-12 completer.seed=2 completer.timeout=180 --config-name=guideline_tool_retrieval
```

## LLM evaluator

To run LLM-based evaluation,

```bash
python scripts/llm_judge_evaluator.py [my_path]/results.jsonl
```
where `my_path` should be an *absolute* path to a subdirectory of `models` where your results are saved.
