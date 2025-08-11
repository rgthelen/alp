# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start - Writing ALP Programs

ALP programs are JSONL files (one JSON object per line) that define data flow graphs. Each line is a node:

### Essential Node Types
1. **@shape** - Define data structures
2. **@fn** - Functions with operations or LLM calls  
3. **@flow** - Connect functions with edges

### Minimal Example Structure
```jsonl
{"kind":"@shape","id":"Input","fields":{"text":"str"}}
{"kind":"@shape","id":"Output","fields":{"result":"str"}}
{"kind":"@fn","id":"process","in":"Input","out":"Output","@op":[["concat",{"items":["Result: ","$in.text"]},{"as":"result"}]],"@expect":{"result":"$result"}}
{"kind":"@flow","edges":[["process",null,{}]]}
```

## Common Operations Reference

### String Operations
- `concat` - Concatenate strings: `["concat",{"items":["Hello ","World"]},{"as":"text"}]`
- `join` - Join with separator: `["join",{"items":["a","b"],"sep":","},{"as":"csv"}]`
- `split` - Split string: `["split",{"text":"a,b","sep":","},{"as":"parts"}]`

### Math Operations  
- Basic: `add`, `sub`, `mul`, `div`, `pow`, `neg`, `abs`, `round`
- Aggregates: `sum`, `avg`, `min`, `max`
- Expression evaluator: `["calc_eval",{"expr":"2+2*3"},{"as":"result"}]`

### JSON Operations
- `json_parse` - Parse JSON: `["json_parse",{"text":"$response.text"},{"as":"data"}]`
- `json_get` - Extract field: `["json_get",{"obj":"$data","path":"field.nested"},{"as":"value"}]`

### I/O Operations (Sandboxed)
- `read_file` - Read file: `["read_file",{"path":"data.txt"},{"as":"content"}]`
- `write_file` - Write file: `["write_file",{"path":"out.txt","text":"$content"}]`
- `http` - HTTP request: `["http",{"method":"GET","url":"$api_url"},{"as":"response"}]`

### LLM Operations
```json
{"@llm":{"task":"summarize","input":{"text":"$doc"},"schema":"Summary"}}
```

## Variable Resolution
- Use `$variable` to reference values
- Dot notation for nested: `$response.data.field`
- Store operation results: `{"as":"variable_name"}`

## Running Programs

```bash
# Basic run
uv run python main.py examples/my_program.alp

# With HTTP permission
ALP_HTTP_ALLOWLIST=api.example.com uv run python main.py examples/my_program.alp

# With file write permission
ALP_IO_ROOT=/tmp ALP_ALLOW_WRITE=true uv run python main.py examples/my_program.alp

# With LLM provider
ALP_MODEL_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-... uv run python main.py examples/my_program.alp
```

## Security Requirements

**Always Required:**
- HTTP calls need `ALP_HTTP_ALLOWLIST=domain1,domain2`
- File writes need `ALP_ALLOW_WRITE=true`
- File I/O restricted to `ALP_IO_ROOT` (default: current dir)
- Tool execution needs explicit allowlists

## Creating New ALP Programs

### Step 1: Define Data Structures
```jsonl
{"kind":"@shape","id":"RequestData","fields":{"query":"str","limit?":"int"},"defaults":{"limit":10}}
```

### Step 2: Create Functions
```jsonl
{"kind":"@fn","id":"fetch_data","in":"RequestData","out":"Response","@const":{"base_url":"https://api.example.com"},"@op":[...operations...]}
```

### Step 3: Connect with Flow
```jsonl
{"kind":"@flow","edges":[["fetch_data","process_data",{}],["process_data","save_results",{}]]}
```

## Common Patterns

### API Integration
```jsonl
{"kind":"@fn","id":"api_call","in":{},"out":"ApiResponse","@const":{"url":"https://api.example.com/data"},"@op":[["http",{"method":"GET","url":"$url"},{"as":"resp"}],["json_parse",{"text":"$resp.text"},{"as":"data"}]]}
```

### Data Processing Pipeline
```jsonl
{"kind":"@fn","id":"pipeline","in":"RawData","out":"Processed","@op":[["operation1",{...},{"as":"step1"}],["operation2",{"input":"$step1"},{"as":"step2"}],["operation3",{"input":"$step2"},{"as":"result"}]]}
```

### Conditional Execution
```jsonl
{"kind":"@flow","edges":[["check","success",{"when":{"eq":["$value.status","ok"]}}],["check","error",{"when":{"ne":["$value.status","ok"]}}]]}
```

## Testing

```bash
# Run test suite
uv run python main.py test/tests.jsonl
```

Test format (JSONL):
```json
{"program":{"kind":"@fn",...},"expect":"expected output","env":{"VAR":"value"}}
```

## Development Tips

1. **Use mock LLM** - No API key needed, auto-generates valid responses
2. **Check examples/** - Reference existing examples for patterns
3. **Validate early** - Use @shape for type checking
4. **Name operations** - Use `{"as":"name"}` for debugging
5. **Test sandboxed** - Always test with security restrictions first

## Architecture Summary

- **VM** (`runtime/vm.py`) - Executes DAG with topological sort
- **Operations** (`runtime/stdlib/`) - Modular operation registry
- **Security** - Sandboxed by default, explicit permissions required
- **Types** - Strong typing with @shape and @def
- **Mock LLM** - Development without API keys