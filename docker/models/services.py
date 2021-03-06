import copy
from docker.errors import create_unexpected_kwargs_error
from docker.types import TaskTemplate, ContainerSpec
from .resource import Model, Collection


class Service(Model):
    """A service."""
    id_attribute = 'ID'

    @property
    def name(self):
        """The service's name."""
        return self.attrs['Spec']['Name']

    @property
    def version(self):
        """
        The version number of the service. If this is not the same as the
        server, the :py:meth:`update` function will not work and you will
        need to call :py:meth:`reload` before calling it again.
        """
        return self.attrs.get('Version').get('Index')

    def remove(self):
        """
        Stop and remove the service.

        Raises:
            :py:class:`docker.errors.APIError`
                If the server returns an error.
        """
        return self.client.api.remove_service(self.id)

    def tasks(self, filters=None):
        """
        List the tasks in this service.

        Args:
            filters (dict): A map of filters to process on the tasks list.
                Valid filters: ``id``, ``name``, ``node``,
                ``label``, and ``desired-state``.

        Returns:
            (:py:class:`list`): List of task dictionaries.

        Raises:
            :py:class:`docker.errors.APIError`
                If the server returns an error.
        """
        if filters is None:
            filters = {}
        filters['service'] = self.id
        return self.client.api.tasks(filters=filters)

    def update(self, **kwargs):
        """
        Update a service's configuration. Similar to the ``docker service
        update`` command.

        Takes the same parameters as :py:meth:`~ServiceCollection.create`.

        Raises:
            :py:class:`docker.errors.APIError`
                If the server returns an error.
        """
        # Image is required, so if it hasn't been set, use current image
        if 'image' not in kwargs:
            spec = self.attrs['Spec']['TaskTemplate']['ContainerSpec']
            kwargs['image'] = spec['Image']

        create_kwargs = _get_create_service_kwargs('update', kwargs)

        return self.client.api.update_service(
            self.id,
            self.version,
            **create_kwargs
        )


class ServiceCollection(Collection):
    """Services on the Docker server."""
    model = Service

    def create(self, image, command=None, **kwargs):
        """
        Create a service. Similar to the ``docker service create`` command.

        Args:
            image (str): The image name to use for the containers.
            command (list of str or str): Command to run.
            args (list of str): Arguments to the command.
            constraints (list of str): Placement constraints.
            container_labels (dict): Labels to apply to the container.
            endpoint_spec (EndpointSpec): Properties that can be configured to
                access and load balance a service. Default: ``None``.
            env (list of str): Environment variables, in the form
                ``KEY=val``.
            labels (dict): Labels to apply to the service.
            log_driver (str): Log driver to use for containers.
            log_driver_options (dict): Log driver options.
            mode (str): Scheduling mode for the service (``replicated`` or
                ``global``). Defaults to ``replicated``.
            mounts (list of str): Mounts for the containers, in the form
                ``source:target:options``, where options is either
                ``ro`` or ``rw``.
            name (str): Name to give to the service.
            networks (list of str): List of network names or IDs to attach
                the service to. Default: ``None``.
            resources (Resources): Resource limits and reservations.
            restart_policy (RestartPolicy): Restart policy for containers.
            stop_grace_period (int): Amount of time to wait for
                containers to terminate before forcefully killing them.
            update_config (UpdateConfig): Specification for the update strategy
                of the service. Default: ``None``
            user (str): User to run commands as.
            workdir (str): Working directory for commands to run.

        Returns:
            (:py:class:`Service`) The created service.

        Raises:
            :py:class:`docker.errors.APIError`
                If the server returns an error.
        """
        kwargs['image'] = image
        kwargs['command'] = command
        create_kwargs = _get_create_service_kwargs('create', kwargs)
        service_id = self.client.api.create_service(**create_kwargs)
        return self.get(service_id)

    def get(self, service_id):
        """
        Get a service.

        Args:
            service_id (str): The ID of the service.

        Returns:
            (:py:class:`Service`): The service.

        Raises:
            :py:class:`docker.errors.NotFound`
                If the service does not exist.
            :py:class:`docker.errors.APIError`
                If the server returns an error.
        """
        return self.prepare_model(self.client.api.inspect_service(service_id))

    def list(self, **kwargs):
        """
        List services.

        Args:
            filters (dict): Filters to process on the nodes list. Valid
                filters: ``id`` and ``name``. Default: ``None``.

        Returns:
            (list of :py:class:`Service`): The services.

        Raises:
            :py:class:`docker.errors.APIError`
                If the server returns an error.
        """
        return [
            self.prepare_model(s)
            for s in self.client.api.services(**kwargs)
        ]


# kwargs to copy straight over to ContainerSpec
CONTAINER_SPEC_KWARGS = [
    'image',
    'command',
    'args',
    'env',
    'workdir',
    'user',
    'labels',
    'mounts',
    'stop_grace_period',
]

# kwargs to copy straight over to TaskTemplate
TASK_TEMPLATE_KWARGS = [
    'resources',
    'restart_policy',
]

# kwargs to copy straight over to create_service
CREATE_SERVICE_KWARGS = [
    'name',
    'labels',
    'mode',
    'update_config',
    'networks',
    'endpoint_spec',
]


def _get_create_service_kwargs(func_name, kwargs):
    # Copy over things which can be copied directly
    create_kwargs = {}
    for key in copy.copy(kwargs):
        if key in CREATE_SERVICE_KWARGS:
            create_kwargs[key] = kwargs.pop(key)
    container_spec_kwargs = {}
    for key in copy.copy(kwargs):
        if key in CONTAINER_SPEC_KWARGS:
            container_spec_kwargs[key] = kwargs.pop(key)
    task_template_kwargs = {}
    for key in copy.copy(kwargs):
        if key in TASK_TEMPLATE_KWARGS:
            task_template_kwargs[key] = kwargs.pop(key)

    if 'container_labels' in kwargs:
        container_spec_kwargs['labels'] = kwargs.pop('container_labels')

    if 'constraints' in kwargs:
        task_template_kwargs['placement'] = {
            'Constraints': kwargs.pop('constraints')
        }

    if 'log_driver' in kwargs:
        task_template_kwargs['log_driver'] = {
            'Name': kwargs.pop('log_driver'),
            'Options': kwargs.pop('log_driver_options', {})
        }

    # All kwargs should have been consumed by this point, so raise
    # error if any are left
    if kwargs:
        raise create_unexpected_kwargs_error(func_name, kwargs)

    container_spec = ContainerSpec(**container_spec_kwargs)
    task_template_kwargs['container_spec'] = container_spec
    create_kwargs['task_template'] = TaskTemplate(**task_template_kwargs)
    return create_kwargs
