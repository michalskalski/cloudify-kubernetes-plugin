import kubernetes
import os

from exceptions import KuberentesApiInitializationFailedError


class KubernetesApiConfiguration(object):

    def __init__(self, ctx, configuration_data):
        self.ctx = ctx
        self.configuration_data = configuration_data

    def _do_prepare_api(self):
        return None

    def prepare_api(self):
        api = self._do_prepare_api()

        if not api:
            raise KuberentesApiInitializationFailedError(
                'Cannot initialize Kubernetes API with {0} configuration and {1} properties'
                .format(self.__class__.__name__, self.configuration_data))

        return api


class BlueprintFileConfiguration(KubernetesApiConfiguration):
    BLUEPRINT_FILE_NAME_KEY = 'blueprint_file_name'

    def _do_prepare_api(self):
        if self.BLUEPRINT_FILE_NAME_KEY in self.configuration_data:
            blueprint_file_name = self.configuration_data[self.BLUEPRINT_FILE_NAME_KEY]

            try:
                manager_file_path = self.ctx.download_resource(blueprint_file_name)

                if manager_file_path and os.path.isfile(os.path.expanduser(manager_file_path)):
                    kubernetes.config.load_kube_config(config_file=manager_file_path)
                    return kubernetes.client
            except Exception as e:
                self.ctx.logger.error('Cannot download config file from blueprint: {0}'.format(str(e)))

        return None


class ManagerFilePathConfiguration(KubernetesApiConfiguration):
    MANAGER_FILE_PATH_KEY = 'manager_file_path'

    def _do_prepare_api(self):
        if self.MANAGER_FILE_PATH_KEY in self.configuration_data:
            manager_file_path = self.configuration_data[self.MANAGER_FILE_PATH_KEY]

            if manager_file_path and os.path.isfile(os.path.expanduser(manager_file_path)):
                kubernetes.config.load_kube_config(config_file=manager_file_path)
                return kubernetes.client

        return None


class FileContentConfiguration(KubernetesApiConfiguration):
    FILE_CONTENT_KEY = 'file_content'

    def _do_prepare_api(self):
        if self.FILE_CONTENT_KEY in self.configuration_data:
            file_content = self.configuration_data[self.FILE_CONTENT_KEY]

            kubernetes.config.kube_config.KubeConfigLoader(config_dict=file_content).load_and_set()
            return kubernetes.client

        return None


class ApiOptionsConfiguration(KubernetesApiConfiguration):
    API_OPTIONS_KEY = 'api_options'
    API_OPTIONS_HOST_KEY = 'host'
    API_OPTIONS_ALL_KEYS = ['host', 'ssl_ca_cert', 'cert_file', 'key_file', 'verify_ssl']

    def _do_prepare_api(self):
        if self.API_OPTIONS_KEY in self.configuration_data:
            api_options = self.configuration_data[self.API_OPTIONS_KEY]

            if self.API_OPTIONS_HOST_KEY not in api_options:
                return None

            api = kubernetes.client
            for key in self.API_OPTIONS_ALL_KEYS:
                if key in api_options:
                    setattr(api.configuration, key, api_options[key])

            return api
        return None


class KubernetesApiConfigurationVariants(KubernetesApiConfiguration):

    def __init__(self, ctx, configuration_data):
        super(KubernetesApiConfigurationVariants, self).__init__(ctx, configuration_data)
        self.variants = (
            BlueprintFileConfiguration,
            ManagerFilePathConfiguration,
            FileContentConfiguration,
            ApiOptionsConfiguration
        )

    def _do_prepare_api(self):
        self.ctx.logger.debug('Checking how Kubernetes API should be configured')

        for variant in self.variants:
            try:
                api_candidate = variant(self.ctx, self.configuration_data).prepare_api()

                self.ctx.logger.debug('Option {0} will be used'.format(variant.__name__))
                return api_candidate
            except KuberentesApiInitializationFailedError:
                self.ctx.logger.debug('Option {0} cannot be used'.format(variant.__name__))

        raise KuberentesApiInitializationFailedError(
            'Cannot initialize Kubernetes API - no suitable configuration variant found for {0} properties'
            .format(self.configuration_data))
