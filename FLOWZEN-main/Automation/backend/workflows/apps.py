from django.apps import AppConfig


class WorkflowsConfig(AppConfig):
    name = "workflows"
    
    def ready(self):
        import logging
        logger = logging.getLogger(__name__)
        try:
            # CRITICAL: Import modules to run @register_node decorators and populate ACTION_REGISTRY
            import workflows.nodes.action_nodes
            import workflows.actions
            logger.info("Workflows app ready: Nodes and Actions registered successfully.")
        except Exception as e:
            logger.error(f"Failed to register nodes/actions: {e}", exc_info=True)
