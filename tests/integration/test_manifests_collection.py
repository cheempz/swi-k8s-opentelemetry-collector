import pytest
import os
import json
from test_utils import get_all_bodies_for_all_sent_content, get_all_resources_for_all_sent_content, has_attribute_with_key_and_value, retry_until_ok, run_shell_command

endpoint = os.getenv("TIMESERIES_MOCK_ENDPOINT", "localhost:8088")
url = f'http://{endpoint}/manifests.json'
pod_name = 'dummy-pod'
namespace_name = 'default'
label_key = 'test-label'
label_value = 'test-label-value'
annotation_key = 'test-annotation'
annotation_value = 'test-annotation-value'


def setup_function():
    run_shell_command(f"kubectl run {pod_name} --labels \"{label_key}={label_value}\" --overrides=\"{{ \\\"apiVersion\\\": \\\"v1\\\", \\\"metadata\\\": {{\\\"annotations\\\": {{ \\\"{annotation_key}\\\":\\\"{annotation_value}\\\" }} }} }}\" --image bash:alpine3.19 -n {namespace_name} -- -ec \"while :; do sleep 5 ; done\"")


def teardown_function():
    run_shell_command(f'kubectl delete pod {pod_name} -n {namespace_name}')


def test_manifests_generated():
    retry_until_ok(url, assert_test_manifest_found, print_failure)


def test_manifests_have_labels_and_annotations():
    retry_until_ok(url, assert_test_manifest_label_and_annotation_found,
                   print_labels_and_annotations_failure)


def test_manifests_have_labels_and_annotations_unchanged():
    retry_until_ok(url, assert_test_manifest_label_and_annotation_unchanged,
                   print_labels_and_annotations_unchanged_failure)


def assert_test_manifest_found(content):
    raw_bodies = get_all_bodies_for_all_sent_content(content)
    for inner_list in raw_bodies:
        for manifest in inner_list:
            if is_correct_manifest(manifest, 'Pod', pod_name, namespace_name):
                return True


def print_failure(content):
    raw_bodies = get_all_bodies_for_all_sent_content(content)
    print(
        f'Failed to find manifest for Pod {pod_name} in Namespace {namespace_name}')
    print('Sent manifests:')
    print(raw_bodies)


def assert_test_manifest_label_and_annotation_found(content):
    resources = get_all_resources_for_all_sent_content(content)
    resource = find_resource_with_specific_manifest(
        resources, 'Pod', pod_name, namespace_name)
    print(resource)

    if resource is not None:
        return (has_attribute_with_key_and_value(resource, f"k8s.pod.labels.{label_key}", label_value) and
                has_attribute_with_key_and_value(resource, f"k8s.pod.annotations.{annotation_key}", annotation_value))
    else:
        print("Resource not found")
        return False


def print_labels_and_annotations_failure(content):
    raw_bodies = get_all_resources_for_all_sent_content(content)
    print(
        f'Failed to find resource for Pod {pod_name} in Namespace {namespace_name} with correct labels and annotations')
    print('Sent resources:')
    print(raw_bodies)


def assert_test_manifest_label_and_annotation_unchanged(content):
    raw_bodies = get_all_bodies_for_all_sent_content(content)
    for inner_list in raw_bodies:
        for raw_manifest in inner_list:
            if is_correct_manifest(raw_manifest, 'Pod', pod_name, namespace_name):
                parsed_manifest = json.loads(raw_manifest)
                if parsed_manifest['metadata']['annotations'][annotation_key] == annotation_value and parsed_manifest['metadata']['labels'][label_key] == label_value:
                    return True
    print("Expected labels and annotations were not found")
    return False


def print_labels_and_annotations_unchanged_failure(content):
    raw_bodies = get_all_bodies_for_all_sent_content(content)
    print(
        f'Failed to find correct labels and annotations in manifest for Pod {pod_name} in Namespace {namespace_name}')
    print('Sent manifests:')
    print(raw_bodies)


def find_resource_with_specific_manifest(raw_resources, kind: str, name: str, namespace: str):
    for inner_list in raw_resources:
        for obj in inner_list:
            scope_logs = obj.get("scopeLogs", [])
            for scope_log in scope_logs:
                log_records = scope_log.get("logRecords", [])
                for log_record in log_records:
                    body = log_record.get("body", {}).get("stringValue", "")
                    if is_correct_manifest(body, kind, name, namespace):
                        return obj["resource"]

    return None


def is_correct_manifest(raw_manifest, kind: str, name: str, namespace: str) -> bool:
    parsed_manifest = json.loads(raw_manifest)
    return parsed_manifest['kind'] == kind and parsed_manifest['metadata']['name'] == name and parsed_manifest['metadata']['namespace'] == namespace
