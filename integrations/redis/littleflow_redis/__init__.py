'''
An integration of littleflow an Redis for remote execution.
'''
__version__=(0,5,0)
__author__='Alex Miłowski'
__author_email__='alex@milowski.com'

from .context import RedisOutputCache, MetadataService
from .remote import RemoteTaskContext, RedisContext, TaskEndListener, TaskStartListener, LifecycleListener, run_workflow, compute_vector, trace_vector, \
                    workflow_archive, restore_workflow, save_workflow, load_workflow, load_workflow_state, workflow_state, is_running, delete_workflow, \
                    terminate_workflow, restart_workflow, get_failures, set_failures
from .wait import WaitTaskListener
from .request import RequestTaskListener
from .auth import create_jwt_credential_actor
from .cli import cli as main
