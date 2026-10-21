"""Static mapping contract: not a replacement for a native Qt test."""
from pathlib import Path

def test_circular_ui_enum_mapping_is_explicit_in_source():
    """Static source contract check, not a substitute for real Qt clicking."""
    import ast
    source=Path(__file__).parents[1]/'app'/'beam_component_editor.py'
    tree=ast.parse(source.read_text())
    mappings={}
    for item in tree.body:
        if isinstance(item,ast.Assign):
            for target in item.targets:
                if isinstance(target,ast.Name) and target.id in {'FA','ENUMS'}:
                    mappings[target.id]=ast.literal_eval(item.value)
    assert {'spiral','full_lateral','circular_lateral','no_extension_reviewed','detailed_extensions'} <= set(mappings['FA'])
    assert {'shape_kind','coverage','area_method','end_condition'} <= mappings['ENUMS']
