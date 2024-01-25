import os
import shutil
import xml.etree.ElementTree as ET

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
    """Analyze proxy configurations to find where each policy is used, including the flow and file."""
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
                            usage_context = {'file': filename, 'flow': flow_name}
                            policy_usage[policy_name].append(usage_context)
            except ET.ParseError as e:
                print(f"Error parsing file {file_path}: {e}")

    return policy_usage

def generate_migration_plan(policy_data, policy_usage, new_policy_prefix, env_cache_resource):
    """Generate a migration plan for cache policies, considering policies in the same flow."""
    migration_plan = []

    for policy_name, policy_info in policy_data.items():
        if policy_info['type'] == 'PopulateCache' and not policy_info['cache_resource']:
            new_name = f"{new_policy_prefix}{policy_name}"
            populate_proxy_files = {usage['file'] for usage in policy_usage.get(policy_name, [])}
            populate_flows = {usage['flow'] for usage in policy_usage.get(policy_name, [])}

            new_populate_policy = {
                'original_name': policy_name,
                'new_name': new_name,
                'type': 'PopulateCache',
                'cache_resource': env_cache_resource,
                'proxy_files': list(populate_proxy_files)
            }
            migration_plan.append(new_populate_policy)

            for lookup_name, lookup_info in policy_data.items():
                if lookup_info['type'] == 'LookupCache' and lookup_info['cache_key'] == policy_info['cache_key']:
                    lookup_proxy_files_flows = {(usage['file'], usage['flow']) for usage in policy_usage.get(lookup_name, [])}
                    intersecting_files_flows = {(file, flow) for file, flow in lookup_proxy_files_flows if file in populate_proxy_files and flow in populate_flows}

                    if intersecting_files_flows:
                        new_lookup_policy = {
                            'original_name': lookup_name,
                            'new_name': f"{new_policy_prefix}{lookup_name}",
                            'type': 'LookupCache',
                            'cache_resource': env_cache_resource,
                            'proxy_files_flows': intersecting_files_flows
                        }
                        migration_plan.append(new_lookup_policy)

    return migration_plan

def create_new_policy_file(policy_info, policies_dir):
    """Create a new policy XML file with environmental cache resource."""
    original_file_path = os.path.join(policies_dir, f"{policy_info['original_name']}.xml")
    new_file_path = os.path.join(policies_dir, f"{policy_info['new_name']}.xml")

    tree = ET.parse(original_file_path)
    root = tree.getroot()

    root.set('name', policy_info['new_name'])
    cache_resource_element = ET.SubElement(root, 'CacheResource')
    cache_resource_element.text = policy_info['cache_resource']

    tree.write(new_file_path)

def add_or_update_policy_in_flow(flow, policy_info, is_lookup_policy):
    """Add or update a policy within a given flow."""
    step_updated = False
    for step in flow.findall('.//Step'):
        policy_name_element = step.find('Name')
        if policy_name_element is not None and policy_name_element.text == policy_info['original_name']:
            if is_lookup_policy and not step_updated:
                new_step = ET.Element('Step')
                new_name = ET.SubElement(new_step, 'Name')
                new_name.text = policy_info['new_name']
                flow.insert(flow.index(step) + 1, new_step)
                step_updated = True
            elif not is_lookup_policy:
                policy_name_element.text = policy_info['new_name']
                step_updated = True

def update_conditions(root, policy_info):
    """Update conditions in the proxy configuration."""
    for condition in root.findall('.//Condition'):
        if policy_info['original_name'] in condition.text:
            condition.text = condition.text.replace(policy_info['original_name'], policy_info['new_name'])

def update_proxy_configuration(proxy_file, policy_info, is_lookup_policy=False):
    """Update proxy configuration for LookupCache and PopulateCache policies and update conditions."""
    tree = ET.parse(proxy_file)
    root = tree.getroot()

    if 'proxy_files_flows' in policy_info:
        # Handle LookupCache policy update
        for file_flow in policy_info['proxy_files_flows']:
            if file_flow[0] == proxy_file:
                for flow in root.findall(f".//Flow[@name='{file_flow[1]}']"):
                    add_or_update_policy_in_flow(flow, policy_info, is_lookup_policy)
    else:
        # Handle PopulateCache policy update
        for flow in root.findall('.//Flow'):
            add_or_update_policy_in_flow(flow, policy_info, is_lookup_policy)

    update_conditions(root, policy_info)

    tree.write(proxy_file)

def apply_migration_plan(migration_plan, policies_dir, proxies_dir):
    """Apply the migration plan to Apigee proxy configurations."""
    for policy_info in migration_plan:
        create_new_policy_file(policy_info, policies_dir)

        if 'proxy_files_flows' in policy_info:
            for file_flow in policy_info['proxy_files_flows']:
                proxy_file_path = os.path.join(proxies_dir, file_flow[0])
                update_proxy_configuration(proxy_file_path, policy_info, policy_info['type'] == 'LookupCache')
        else:
            for proxy_file in policy_info['proxy_files']:
                proxy_file_path = os.path.join(proxies_dir, proxy_file)
                update_proxy_configuration(proxy_file_path, policy_info, policy_info['type'] == 'LookupCache')

    print("Migration plan applied to Apigee proxy configurations.")

def main():
    policies_dir = input("Enter the path to your Apigee policies directory: ")
    proxies_dir = input("Enter the path to your Apigee proxies directory: ")
    new_policy_prefix = input("Enter the prefix for new policies: ")
    env_cache_resource = input("Enter the name of the environmental cache resource: ")

    policy_data = {}
    for filename in os.listdir(policies_dir):
        if filename.endswith(".xml"):
            file_path = os.path.join(policies_dir, filename)
            policy_info = parse_policy(file_path)
            policy_data[policy_info['name']] = policy_info

    policy_usage = analyze_proxy(proxies_dir, policy_data.keys())
    migration_plan = generate_migration_plan(policy_data, policy_usage, new_policy_prefix, env_cache_resource)

    shutil.copytree(policies_dir, f"{policies_dir}_backup")
    shutil.copytree(proxies_dir, f"{proxies_dir}_backup")

    apply_migration_plan(migration_plan, policies_dir, proxies_dir)

if __name__ == "__main__":
    main()
