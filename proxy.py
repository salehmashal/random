import os
import shutil
from lxml import etree as ET

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
        for usage in policy_info['usage']:
            context = usage['context'].split(' ')[0]
            if context in ['ProxyEndpoint', 'TargetEndpoint']:
                proxy_name = usage['context'].split('(')[1].rstrip(')')
                proxy_file = os.path.join(proxies_dir, f"{proxy_name}.xml")
                update_proxy_configuration(proxy_file, policy_info)

def main():
    policies_dir = "path/to/apigee/policies"
    proxies_dir = "path/to/apigee/proxies"

    # Assuming migration_plan is obtained as before
    migration_plan = generate_migration_plan(policy_data, policy_usage)

    # Backup original configurations
    shutil.copytree(policies_dir, f"{policies_dir}_backup")
    shutil.copytree(proxies_dir, f"{proxies_dir}_backup")

    # Apply the migration plan
    apply_migration_plan(migration_plan, policies_dir, proxies_dir)

    print("Migration plan applied to Apigee proxy configurations.")

if __name__ == "__main__":
    main()
