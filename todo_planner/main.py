import os
import re
from todo_planner.safe_todoist_api import SafeTodoistAPI
import logging

access_token = os.getenv('TODOIST_ACCESS_TOKEN')
api = SafeTodoistAPI(access_token)
active_tasks_cache = None
inactive_tasks_cache = None


def get_task_from_tasks(task_id, tasks):
    if not tasks:
        return None
    for task in tasks:
        if task.id == task_id:
            return task
    return None


def get_active_tasks():
    global active_tasks_cache
    if active_tasks_cache is None:
        active_tasks_cache = api.get_tasks()
    return active_tasks_cache


def get_task(task_id):
    global inactive_tasks_cache
    tasks = get_active_tasks()
    task = get_task_from_tasks(task_id, tasks)
    if task is None:
        task = get_task_from_tasks(task_id, inactive_tasks_cache)
    if task is None:
        task = api.get_task(task_id)
    return task


def extract_id_from_string(string):
    match = re.search(r'https://(app.)?todoist.com/showTask\?id=(\d+)', string)
    return match.group(2) if match else None


def search_dependencies(description):
    task_ids = []
    for line in description.split('\n'):
        if line.startswith('<'):
            task_id = extract_id_from_string(line)
            if task_id:
                task_ids.append(task_id)
    return set(task_ids)


def get_existing_tasks(task_ids):
    if not task_ids:
        return []
    tasks = []
    for task_id in task_ids:
        task = get_task(task_id)
        if task:
            tasks.append(task)
    return tasks


def get_dependencies(task):
    task_ids = search_dependencies(task.description)
    return get_existing_tasks(task_ids)


def get_undone_tasks():
    return api.get_tasks(filter='!@next')


def get_next_tasks():
    return api.get_tasks(filter='@next')


def get_dependents(task_id, addditional_filter=''):
    tasks = get_active_tasks()
    dependents = []
    for task in tasks:
        dependencies = get_dependencies(task)
        if any(dependency.id == task_id for dependency in dependencies):
            dependents.append(task)
    return dependents


def add_label(task, label):
    labels = task.labels
    if label not in labels:
        labels.append(label)
        try:
            api.update_task(
                task_id=task.id, labels=labels)
            return True
        except Exception as error:
            logging.info(error)
    return False


def remove_label(task, label):
    labels = task.labels
    if label in labels:
        labels.remove(label)
        try:
            api.update_task(
                task_id=task.id, labels=labels)
            return True
        except Exception as error:
            logging.info(error)
    return False


def is_labeling_event(event, label_name):
    if event['event_name'] != 'item:updated':
        return False
    labels = event['event_data']['labels']
    old_labels = event['event_data_extra']['old_item']['labels']
    label_set = set(labels)
    old_label_set = set(old_labels)
    logging.info(label_set, old_label_set)
    if (label_set - old_label_set == {label_name} or
            old_label_set - label_set == {label_name}):
        return True
    return False


def update_next_label(task, dependencies=None):
    if dependencies is None:
        dependencies = get_dependencies(task)
    all_done = True
    for dependency in dependencies:
        dependent_task = api.get_task(dependency.id)
        if not dependent_task.is_completed:
            all_done = False
            break
    if all_done:
        if remove_label(task, 'next'):
            logging.info("Remove next label from task: {}".format(task.id))
    else:
        if add_label(task, 'next'):
            logging.info("Add next label to task: {}".format(task.id))
    return


def event_handler(event):
    event_name = event['event_name']
    if event_name == 'item:completed':
        event_task_completed(event)
    elif event_name == 'item:updated':
        event_task_updated(event)
    elif event_name == 'item:added':
        event_task_added(event)
    elif event_name == 'item:uncompleted':
        event_task_uncompleted(event)
    elif event_name == 'item:deleted':
        event_task_deleted(event)
    else:
        logging.info("Unknown event: {}".format(event_name))
    return


def event_task_added(event):
    task_id = event['event_data']['id']
    logging.info('event_task_added task_id: {}'.format(task_id))
    task = api.get_task(task_id)
    dependencis = search_dependencies(event['event_data']['description'])
    update_next_label(task, dependencis)


def event_task_updated(event):
    task_id = event['event_data']['id']
    logging.info('event_task_updated task_id: {}'.format(task_id))
    task = api.get_task(task_id)
    dependencis = search_dependencies(event['event_data']['description'])
    old_dependencis = search_dependencies(
        event['event_data_extra']['old_item']['description'])
    if dependencis == old_dependencis:
        return
    # dependencies updated
    update_next_label(task)


def event_task_completed(event):
    event_data = event['event_data']
    task_id = event_data['id']
    logging.info('event_task_completed task_id: {}'.format(task_id))

    # find tasks with next label and depended on this task
    tasks = get_dependents(task_id, '& @next')
    logging.info('dependents tasks: {} of {}'.format(tasks, task_id))
    for task in tasks:
        update_next_label(task)


def event_task_uncompleted(event):
    event_data = event['event_data']
    task_id = event_data['id']
    logging.info('event_task_uncompleted task_id: {}'.format(task_id))

    # find tasks with next label and depended on this task
    tasks = get_dependents(task_id, '& !@next')
    for task in tasks:
        update_next_label(task)


def event_task_deleted(event):
    event_data = event['event_data']
    task_id = event_data['id']
    logging.info('event_task_deleted task_id: {}'.format(task_id))

    # find tasks with next label and depended on this task
    tasks = get_dependents(task_id, '& @next')
    for task in tasks:
        update_next_label(task)


def remove_next_label_from_tasks_with_no_dependencies():
    next_tasks = get_next_tasks()
    for task in next_tasks:
        dependencies = get_dependencies(task)
        if dependencies:
            dependency_ids = [dependency.id for dependency in dependencies]
            logging.info("Task {} has dependencies {}".format(
                task.id, dependency_ids))
        all_done = True
        for dependency in dependencies:
            dependent_task = api.get_task(dependency.id)
            if not dependent_task.is_completed:
                all_done = False
                break
        if all_done:
            if remove_label(task, 'next'):
                logging.info("Remove next label from task: ", task.id)


def add_next_label_to_tasks_with_undone_dependencies():
    undone_tasks = get_undone_tasks()
    for task in undone_tasks:
        dependencies = get_dependencies(task)
        all_done = True
        for dependency in dependencies:
            dependent_task = api.get_task(dependency.id)
            if not dependent_task.is_completed:
                all_done = False
                break
        if not all_done:
            if add_label(task, 'next'):
                logging.info("Add next label to task: ", task.id)


if __name__ == "__main__":
    print("main")
