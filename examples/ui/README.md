# ALP UI System

A modular UI system for ALP programs using Gradio.

## Architecture

The UI system follows **separation of concerns**:
- Core ALP programs remain unchanged
- UI orchestrators are separate ALP programs
- UI operations are implemented as standard ALP operations

## Examples

### calculator.alp
A complete calculator with UI that evaluates mathematical expressions.
```bash
uv run python main.py examples/ui/calculator.alp
# Opens at http://localhost:7864
```

### simple_test.alp  
A minimal UI example for testing the Gradio integration.
```bash
uv run python main.py examples/ui/simple_test.alp
# Opens at http://localhost:7862
```

## UI Operations

- `ui_create` - Initialize a UI with title and theme
- `ui_add_input` - Add input components (textbox, number, slider, dropdown)
- `ui_add_output` - Add output components (textbox, json, markdown)
- `ui_set_handler` - Connect UI to ALP functions
- `ui_launch` - Start the Gradio server
- `ui_wait` - Keep the UI running

## Creating a UI

### Input Mapping Rules

The UI system automatically maps UI inputs to function inputs based on the function signature:

1. **Single typed input** (`"in": "ShapeType"`):
   - UI input names should match the shape's field names
   - Example: Function expects `CalcInput` with field `expr`, UI should have input named `expr`

2. **Named inputs** (`"in": {"field1": "type1", "field2": "type2"}`):
   - UI input names should match the function's input field names

3. **No inputs** (function has no `"in"` declaration):
   - Function will be called with no input data

### Example: Calculator UI

1. Define your data processing function:
```json
{"kind":"@shape","id":"CalcInput","fields":{"expr":"str"}}
{"kind":"@shape","id":"CalcResult","fields":{"value":"float"}}
{"kind":"@fn","id":"calculate","in":"CalcInput","out":"CalcResult","@op":[
  ["calc_eval",{"expr":"$in.expr"},{"as":"result"}]
]}
```

2. Create the UI with matching input name:
```json
{"kind":"@fn","id":"create_ui","@op":[
  ["ui_create",{"title":"Calculator"}],
  ["ui_add_input",{"name":"expr","type":"textbox","label":"Expression"}],
  ["ui_add_output",{"name":"result","type":"json"}],
  ["ui_set_handler",{"function":"calculate","inputs":["expr"],"outputs":["result"]}],
  ["ui_launch",{"port":7860}],
  ["ui_wait",{}]
]}
```

Note: The UI input is named `expr` to match the `CalcInput` field name.

## Importing Other ALP Files

Use `@import` to load functions from other files:
```json
{"kind":"@import","path":"../calculator.alp"}
```

Then reference the imported functions in your UI handlers.

## Future Enhancements

- Support for multiple UI frameworks (web, CLI)
- Dynamic component generation from @shape definitions
- Multi-page applications
- Real-time updates and streaming