import json
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
rule_based_dir = os.path.join(current_dir, 'rule-based')
if rule_based_dir not in sys.path:
    sys.path.insert(0, rule_based_dir)

from models import ApiSpec
from test_case_generator import TestCaseGenerator
from test_code_renderer import TestCodeRenderer

def process_spec(spec_path: str):
    if not os.path.exists(spec_path):
        print(f"Error: File not found: {spec_path}")
        return

    print(f"Reading spec: {spec_path}")
    with open(spec_path, 'r', encoding='utf-8') as f:
        spec_data = json.load(f)
        
    spec = ApiSpec(spec_data)
    
    # Normally read from local ConfigLoader, but we'll use dummy fallbacks or envs here
    spec.username = os.getenv("TEST_USERNAME", "dummy_user")
    spec.password = os.getenv("TEST_PASSWORD", "dummy_pass")
    
    generator = TestCaseGenerator()
    renderer = TestCodeRenderer()
    
    test_cases = generator.generate(spec)
    print(f"Generated {len(test_cases)} rule-based test cases.")
    
    source_code = renderer.render(spec, test_cases)
    
    # Derive output filename from input filename
    base_name = os.path.basename(spec_path).replace('.json', '')
    if not base_name.startswith('test_'):
        file_name = f"test_{base_name}.py"
    else:
        file_name = f"{base_name}.py"
        
    base_dir = os.path.dirname(current_dir)
    tests_dir = os.path.join(base_dir, 'tests')
    os.makedirs(tests_dir, exist_ok=True)
    
    output_path = os.path.join(tests_dir, file_name)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(source_code)
        
    print(f"Generated: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_spec(sys.argv[1])
    else:
        print("Usage: python generators/test_generator_app.py api-specs/<filename.json>")
