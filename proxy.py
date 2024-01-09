import os
import shutil
from lxml import etree as ET

def parse_policy(file_path):
    """Parse an individual policy file to extract cache key and resource information."""
    tree = ET.parse(file_path)
    root = tree.getroot()
    return {
        'name': root.get('name'),
        'type': root.tag,
        'cache_key': (root.find('.//CacheKey').text or '').strip() if root.find('.//CacheKey') is not None else None,
        'cache_resource': root.find('.//CacheResource').text if root.find('.//CacheResource') is not None else None
    }

def analyze_proxy(directory, policy_names):
    """Analyze proxy configurations to find where each policy is used."""
    policy_usage = {name: [] for name in policy_names}

    for filename in os.listdir(directory):
        if filename.endswith(".xml"):
            file_path = os.path.join(directory, filename)
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()

                for flow in root.findall('.//Flow'):
                    flow_name = flow.get('name')
                    for step in flow.findall('.//Step'):
                        policy_name = step.find('Name').text
                        if policy_name in policy_names:
                            line_number = step.sourceline
                            context = f"{root.tag} ({flow_name})"
                            policy_usage[policy_name].append({'context': context, 'line': line_number})
            except ET.ParseError as e:
                print(f"Error parsing file {file_path}: {e}")

    return policy_usage


def generate_migration_plan(policy_data, policy_usage):
    """Generate a migration plan for cache policies."""
    migration_plan = []

    for policy_name, policy_info in policy_data.items():
        if policy_info['type'] == 'PopulateCache' and not policy_info['cache_resource']:
            # Generate new PopulateCache policy with environmental cache resource
            new_populate_policy = {
                'original_name': policy_name,
                'new_name': f"{policy_name}_env",
                'type': 'PopulateCache',
                'cache_resource': 'environmental_cache',  # Replace with actual resource name
                'proxy_files': [usage['proxy_file'] for usage in policy_usage.get(policy_name, [])]
            }
            migration_plan.append(new_populate_policy)

            # Find and clone related LookupCache policies
            for lookup_name, lookup_info in policy_data.items():
                if lookup_info['type'] == 'LookupCache' and lookup_info['cache_key'] == policy_info['cache_key']:
                    new_lookup_policy = {
                        'original_name': lookup_name,
                        'new_name': f"{lookup_name}_env",
                        'type': 'LookupCache',
                        'cache_resource': 'environmental_cache',  # Replace with actual resource name
                        'proxy_files': [usage['proxy_file'] for usage in policy_usage.get(lookup_name, [])]
                    }
                    migration_plan.append(new_lookup_policy)

    return migration_plan
    
def create_new_policy_file(policy_info, policies_dir):
    """Create a new policy XML file with environmental cache resource."""
    original_file_path = os.path.join(policies_dir, f"{policy_info['original_name']}.xml")
    new_file_path = os.path.join(policies_dir, f"{policy_info['new_name']}.xml")

    tree = ET.parse(original_file_path)
    root = tree.getroot()

    # Update policy name and CacheResource
    root.set('name', policy_info['new_name'])
    cache_resource_element = ET.SubElement(root, 'CacheResource')
    cache_resource_element.text = policy_info['cache_resource']

    tree.write(new_file_path)

def update_proxy_configuration(proxy_file, policy_info):
    """Update proxy configuration to include the new policy."""
    tree = ET.parse(proxy_file)
    root = tree.getroot()

    for step in root.findall('.//Step'):
        if step.find('Name').text == policy_info['original_name']:
            # Duplicate the step for the new policy
            new_step = ET.Element('Step')
            new_name = ET.SubElement(new_step, 'Name')
            new_name.text = policy_info['new_name']
            step.addnext(new_step)

    tree.write(proxy_file)

def apply_migration_plan(migration_plan, policies_dir, proxies_dir):
    """Apply the migration plan to Apigee proxy configurations."""
    for policy_info in migration_plan:
        # Create new policy files
        create_new_policy_file(policy_info, policies_dir)

        # Update proxy configurations
        for proxy_file in policy_info['proxy_files']:
            proxy_file_path = os.path.join(proxies_dir, proxy_file)
            update_proxy_configuration(proxy_file_path, policy_info)

def main():
    policies_dir = "path/to/apigee/policies"
    proxies_dir = "path/to/apigee/proxies"

    # Parsing policies and collecting names
    policy_data = {}
    for filename in os.listdir(policies_dir):
        if filename.endswith(".xml"):
            file_path = os.path.join(policies_dir, filename)
            policy_info = parse_policy(file_path)
            policy_data[policy_info['name']] = policy_info

    # Analyzing proxy for policy usage
    policy_usage = analyze_proxy(proxies_dir, policy_data.keys())

    # Generate migration plan
    migration_plan = generate_migration_plan(policy_data, policy_usage)

    # Backup original configurations
    shutil.copytree(policies_dir, f"{policies_dir}_backup")
    shutil.copytree(proxies_dir, f"{proxies_dir}_backup")

    # Apply the migration plan
    apply_migration_plan(migration_plan, policies_dir, proxies_dir)

    print("Migration plan applied to Apigee proxy configurations.")

if __name__ == "__main__":
    main()
