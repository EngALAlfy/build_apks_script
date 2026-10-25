"""Single project pipeline; failures propagate to the coordinator."""
import os
from modules import git_module, file_module, flutter_module
from modules.process_runner import check_cancelled

def build_project(project, global_time, on_stage=None, on_artifact=None):
    emit = on_stage or (lambda stage: None)
    emit('Syncing source')
    git_module.git_clone(project)
    if os.getenv('CLEAN_BUILD', 'true') == 'true':
        emit('Cleaning')
        flutter_module.clean(project)
    emit('Resolving dependencies')
    flutter_module.pub_get(project)
    flutter_module.intl_generate(project)
    artifacts = {}
    builders = {'debug': flutter_module.build_debug, 'release': flutter_module.build_release,
                'appbundle': flutter_module.build_appbundle}
    for kind in os.environ.get('BUILD_TYPES', 'release').split(','):
        check_cancelled()
        emit(f'Building {kind}')
        if kind not in builders:
            raise ValueError(f'Unknown build type: {kind}')
        builders[kind](project)
        check_cancelled()
        artifact = file_module.copy_files(project, global_time, kind)
        if not artifact:
            raise FileNotFoundError(f'Expected {kind} artifact was not produced for {project}.')
        artifacts[kind] = artifact
        if on_artifact:
            on_artifact(kind, artifact)
        emit(f'Collected {kind}')
    return artifacts
