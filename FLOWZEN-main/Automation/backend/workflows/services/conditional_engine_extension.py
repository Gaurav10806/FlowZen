"""
Conditional Engine Extension

This module provides minimal extensions to the execution engine
to support conditional node branching without modifying core logic.
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class ConditionalEngineExtension:
    """
    Extension to handle conditional and router node execution paths.
    
    This class provides helper methods to process conditional and router node results
    and determine the correct execution paths without modifying the core engine.
    """
    
    @staticmethod
    def process_conditional_result(node_output: Dict[str, Any], edges: List[Dict[str, Any]], node_id: str) -> List[str]:
        """
        Process conditional or router node output and determine next nodes to execute.
        
        Args:
            node_output: Output from conditional or router node execution
            edges: All workflow edges
            node_id: ID of the conditional/router node
            
        Returns:
            List of node IDs that should be executed next
        """
        # Check if this is a conditional node result
        condition_result = node_output.get('condition_result')
        if condition_result:
            return ConditionalEngineExtension._process_conditional_node(
                condition_result, edges, node_id
            )
        
        # Check if this is a router node result
        router_result = node_output.get('router_result')
        if router_result:
            return ConditionalEngineExtension._process_router_node(
                router_result, edges, node_id
            )
        
        # Check if this is a parallel fork result
        fork_result = node_output.get('fork_result')
        if fork_result:
            return ConditionalEngineExtension._process_fork_node(
                fork_result, edges, node_id
            )
        
        # Check if this is a parallel merge result
        merge_result = node_output.get('merge_result')
        if merge_result:
            return ConditionalEngineExtension._process_merge_node(
                merge_result, edges, node_id
            )
        
        # Not a conditional or router node, use standard edge processing
        return ConditionalEngineExtension._get_standard_next_nodes(edges, node_id)
    
    @staticmethod
    def _process_conditional_node(condition_result: Dict[str, Any], edges: List[Dict[str, Any]], node_id: str) -> List[str]:
        """
        Process conditional node result.
        
        Args:
            condition_result: Conditional node result data
            edges: All workflow edges
            node_id: ID of the conditional node
            
        Returns:
            List of next node IDs
        """
        execution_path = condition_result.get('execution_path', 'true')
        logger.info(f"Conditional node {node_id} result: {execution_path}")
        
        # Find edges from this conditional node
        outgoing_edges = [
            edge for edge in edges 
            if (edge.get('source') == node_id or edge.get('from') == node_id)
        ]
        
        next_nodes = []
        
        for edge in outgoing_edges:
            edge_condition = edge.get('condition')
            target_node = edge.get('target') or edge.get('to')
            
            if not target_node:
                continue
            
            # If edge has no condition, it's a fallback path
            if edge_condition is None:
                next_nodes.append(target_node)
                continue
            
            # Check if edge condition matches execution path
            if edge_condition == execution_path:
                next_nodes.append(target_node)
            elif edge_condition == 'true' and execution_path == 'true':
                next_nodes.append(target_node)
            elif edge_condition == 'false' and execution_path == 'false':
                next_nodes.append(target_node)
        
        # If no conditional edges matched, try fallback edges (no condition)
        if not next_nodes:
            fallback_edges = [
                edge for edge in outgoing_edges 
                if edge.get('condition') is None
            ]
            for edge in fallback_edges:
                target_node = edge.get('target') or edge.get('to')
                if target_node:
                    next_nodes.append(target_node)
        
        logger.debug(f"Conditional node {node_id} -> next nodes: {next_nodes}")
        return next_nodes
    
    @staticmethod
    def _process_router_node(router_result: Dict[str, Any], edges: List[Dict[str, Any]], node_id: str) -> List[str]:
        """
        Process router node result.
        
        Args:
            router_result: Router node result data
            edges: All workflow edges
            node_id: ID of the router node
            
        Returns:
            List of next node IDs
        """
        selected_path = router_result.get('selected_path', 'default')
        matched_paths = router_result.get('matched_paths', [])
        default_path = router_result.get('default_path', 'default')
        
        logger.info(f"Router node {node_id} selected path: {selected_path}")
        
        # Find edges from this router node
        outgoing_edges = [
            edge for edge in edges 
            if (edge.get('source') == node_id or edge.get('from') == node_id)
        ]
        
        next_nodes = []
        
        # First, try to match the selected path
        for edge in outgoing_edges:
            edge_condition = edge.get('condition')
            target_node = edge.get('target') or edge.get('to')
            
            if not target_node:
                continue
            
            # Check if edge condition matches selected path
            if edge_condition == selected_path:
                next_nodes.append(target_node)
        
        # If no edges matched the selected path, try fallback edges (no condition)
        if not next_nodes:
            fallback_edges = [
                edge for edge in outgoing_edges 
                if edge.get('condition') is None
            ]
            for edge in fallback_edges:
                target_node = edge.get('target') or edge.get('to')
                if target_node:
                    next_nodes.append(target_node)
        
        logger.debug(f"Router node {node_id} -> next nodes: {next_nodes}")
        return next_nodes
    
    @staticmethod
    def _process_fork_node(fork_result: Dict[str, Any], edges: List[Dict[str, Any]], node_id: str) -> List[str]:
        """
        Process parallel fork node result.
        
        Args:
            fork_result: Fork node result data
            edges: All workflow edges
            node_id: ID of the fork node
            
        Returns:
            List of next node IDs (all branches)
        """
        branch_executions = fork_result.get('branch_executions', [])
        
        logger.info(f"Fork node {node_id} created {len(branch_executions)} branches")
        
        # Find edges from this fork node
        outgoing_edges = [
            edge for edge in edges 
            if (edge.get('source') == node_id or edge.get('from') == node_id)
        ]
        
        next_nodes = []
        
        # For each branch, find matching edges
        for branch_info in branch_executions:
            branch_id = branch_info.get('branch_id')
            
            for edge in outgoing_edges:
                edge_condition = edge.get('condition')
                target_node = edge.get('target') or edge.get('to')
                
                if not target_node:
                    continue
                
                # Check if edge condition matches branch ID
                if edge_condition == branch_id:
                    next_nodes.append(target_node)
                elif edge_condition is None:
                    # No condition - this edge applies to all branches
                    next_nodes.append(target_node)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_next_nodes = []
        for node in next_nodes:
            if node not in seen:
                seen.add(node)
                unique_next_nodes.append(node)
        
        logger.debug(f"Fork node {node_id} -> next nodes: {unique_next_nodes}")
        return unique_next_nodes
    
    @staticmethod
    def _process_merge_node(merge_result: Dict[str, Any], edges: List[Dict[str, Any]], node_id: str) -> List[str]:
        """
        Process parallel merge node result.
        
        Args:
            merge_result: Merge node result data
            edges: All workflow edges
            node_id: ID of the merge node
            
        Returns:
            List of next node IDs
        """
        successful_branches = merge_result.get('successful_branches', 0)
        total_branches = merge_result.get('total_branches', 0)
        
        logger.info(f"Merge node {node_id} completed: {successful_branches}/{total_branches} branches successful")
        
        # Find edges from this merge node (standard processing)
        outgoing_edges = [
            edge for edge in edges 
            if (edge.get('source') == node_id or edge.get('from') == node_id)
        ]
        
        next_nodes = []
        
        for edge in outgoing_edges:
            target_node = edge.get('target') or edge.get('to')
            edge_condition = edge.get('condition')
            
            if not target_node:
                continue
            
            # Merge nodes typically don't use conditions, but support them
            if edge_condition is None:
                next_nodes.append(target_node)
            else:
                # Could support conditions like "success", "partial", "failed"
                merge_status = "success" if successful_branches > 0 else "failed"
                if edge_condition == merge_status:
                    next_nodes.append(target_node)
        
        logger.debug(f"Merge node {node_id} -> next nodes: {next_nodes}")
        return next_nodes
    
    @staticmethod
    def _get_standard_next_nodes(edges: List[Dict[str, Any]], node_id: str) -> List[str]:
        """
        Get next nodes using standard (non-conditional) edge processing.
        
        Args:
            edges: All workflow edges
            node_id: Current node ID
            
        Returns:
            List of next node IDs
        """
        next_nodes = []
        
        for edge in edges:
            source = edge.get('source') or edge.get('from')
            target = edge.get('target') or edge.get('to')
            
            if source == node_id and target:
                # Only follow edges without conditions for standard nodes
                if edge.get('condition') is None:
                    next_nodes.append(target)
        
        return next_nodes
    
    @staticmethod
    def is_conditional_node(node_config: Dict[str, Any]) -> bool:
        """
        Check if a node is a conditional, router, or parallel node.
        
        Args:
            node_config: Node configuration from workflow JSON
            
        Returns:
            True if node is conditional, router, or parallel
        """
        node_type = node_config.get('type', '')
        return node_type in ['conditional', 'if_else', 'router', 'switch', 'parallel_fork', 'parallel_merge', 'fork', 'merge']
    
    @staticmethod
    def validate_conditional_edges(workflow_graph: Dict[str, Any]) -> List[str]:
        """
        Validate conditional and router node edges in a workflow.
        
        Args:
            workflow_graph: Complete workflow graph
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        nodes = {n.get('id'): n for n in workflow_graph.get('nodes', [])}
        edges = workflow_graph.get('edges', [])
        
        # Find conditional and router nodes
        conditional_nodes = [
            node_id for node_id, node in nodes.items()
            if ConditionalEngineExtension.is_conditional_node(node)
        ]
        
        for node_id in conditional_nodes:
            node_type = nodes[node_id].get('type', '')
            
            # Find outgoing edges
            outgoing_edges = [
                edge for edge in edges
                if (edge.get('source') == node_id or edge.get('from') == node_id)
            ]
            
            if not outgoing_edges:
                errors.append(f"{node_type.title()} node '{node_id}' has no outgoing edges")
                continue
            
            if node_type in ['conditional', 'if_else']:
                # Validate conditional node paths
                errors.extend(ConditionalEngineExtension._validate_conditional_paths(
                    node_id, outgoing_edges
                ))
            elif node_type in ['router', 'switch']:
                # Validate router node paths
                errors.extend(ConditionalEngineExtension._validate_router_paths(
                    node_id, nodes[node_id], outgoing_edges
                ))
            elif node_type in ['parallel_fork', 'fork']:
                # Validate parallel fork node paths
                errors.extend(ConditionalEngineExtension._validate_fork_paths(
                    node_id, nodes[node_id], outgoing_edges
                ))
            elif node_type in ['parallel_merge', 'merge']:
                # Validate parallel merge node paths
                errors.extend(ConditionalEngineExtension._validate_merge_paths(
                    node_id, nodes[node_id], outgoing_edges
                ))
        
        return errors
    
    @staticmethod
    def _validate_conditional_paths(node_id: str, outgoing_edges: List[Dict[str, Any]]) -> List[str]:
        """
        Validate conditional node paths.
        
        Args:
            node_id: Conditional node ID
            outgoing_edges: Outgoing edges from the node
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Check for true/false paths
        has_true_path = False
        has_false_path = False
        has_fallback = False
        
        for edge in outgoing_edges:
            condition = edge.get('condition')
            
            if condition == 'true':
                has_true_path = True
            elif condition == 'false':
                has_false_path = True
            elif condition is None:
                has_fallback = True
        
        # Warn if missing paths (not errors, as fallback is allowed)
        if not has_true_path and not has_fallback:
            errors.append(f"Conditional node '{node_id}' missing TRUE path")
        
        if not has_false_path and not has_fallback:
            errors.append(f"Conditional node '{node_id}' missing FALSE path")
        
        return errors
    
    @staticmethod
    def _validate_router_paths(node_id: str, node_config: Dict[str, Any], outgoing_edges: List[Dict[str, Any]]) -> List[str]:
        """
        Validate router node paths.
        
        Args:
            node_id: Router node ID
            node_config: Router node configuration
            outgoing_edges: Outgoing edges from the node
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Get expected paths from router configuration
        params = node_config.get('params', {})
        rules = params.get('rules', [])
        default_path = params.get('default_path', 'default')
        
        expected_paths = set()
        for rule in rules:
            if isinstance(rule, dict) and 'name' in rule:
                expected_paths.add(rule['name'])
        
        if default_path:
            expected_paths.add(default_path)
        
        # Check which paths have edges
        edge_conditions = set()
        has_fallback = False
        
        for edge in outgoing_edges:
            condition = edge.get('condition')
            if condition is None:
                has_fallback = True
            else:
                edge_conditions.add(condition)
        
        # Check for missing paths
        missing_paths = expected_paths - edge_conditions
        if missing_paths and not has_fallback:
            errors.append(f"Router node '{node_id}' missing edges for paths: {list(missing_paths)}")
        
        # Check for unexpected paths
        unexpected_paths = edge_conditions - expected_paths
        if unexpected_paths:
            errors.append(f"Router node '{node_id}' has edges for undefined paths: {list(unexpected_paths)}")
        
        return errors
    
    @staticmethod
    def _validate_fork_paths(node_id: str, node_config: Dict[str, Any], outgoing_edges: List[Dict[str, Any]]) -> List[str]:
        """
        Validate parallel fork node paths.
        
        Args:
            node_id: Fork node ID
            node_config: Fork node configuration
            outgoing_edges: Outgoing edges from the node
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Get expected branches from fork configuration
        params = node_config.get('params', {})
        branch_count = params.get('branch_count', 2)
        branch_names = params.get('branch_names', [])
        
        # Generate expected branch names if not provided
        if not branch_names:
            branch_names = [f"branch_{i+1}" for i in range(branch_count)]
        else:
            branch_names = branch_names[:branch_count]  # Limit to branch_count
        
        expected_branches = set(branch_names)
        
        # Check which branches have edges
        edge_conditions = set()
        has_fallback = False
        
        for edge in outgoing_edges:
            condition = edge.get('condition')
            if condition is None:
                has_fallback = True
            else:
                edge_conditions.add(condition)
        
        # Check for missing branches
        missing_branches = expected_branches - edge_conditions
        if missing_branches and not has_fallback:
            errors.append(f"Fork node '{node_id}' missing edges for branches: {list(missing_branches)}")
        
        # Check for unexpected branches
        unexpected_branches = edge_conditions - expected_branches
        if unexpected_branches:
            errors.append(f"Fork node '{node_id}' has edges for undefined branches: {list(unexpected_branches)}")
        
        return errors
    
    @staticmethod
    def _validate_merge_paths(node_id: str, node_config: Dict[str, Any], outgoing_edges: List[Dict[str, Any]]) -> List[str]:
        """
        Validate parallel merge node paths.
        
        Args:
            node_id: Merge node ID
            node_config: Merge node configuration
            outgoing_edges: Outgoing edges from the node
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Merge nodes typically have simple outgoing edges
        # Check that there are outgoing edges (merge should lead somewhere)
        if not outgoing_edges:
            errors.append(f"Merge node '{node_id}' has no outgoing edges")
        
        # Check for unsupported conditions on merge node edges
        for edge in outgoing_edges:
            condition = edge.get('condition')
            if condition and condition not in ['success', 'failed', 'partial']:
                errors.append(f"Merge node '{node_id}' has unsupported edge condition: '{condition}'")
        
        return errors
    
    @staticmethod
    def get_conditional_paths_info(workflow_graph: Dict[str, Any]) -> Dict[str, Dict[str, List[str]]]:
        """
        Get information about conditional and router paths in a workflow.
        
        Args:
            workflow_graph: Complete workflow graph
            
        Returns:
            Dict mapping conditional/router node IDs to their path information
        """
        nodes = {n.get('id'): n for n in workflow_graph.get('nodes', [])}
        edges = workflow_graph.get('edges', [])
        
        path_info = {}
        
        # Find conditional and router nodes
        branching_nodes = [
            node_id for node_id, node in nodes.items()
            if ConditionalEngineExtension.is_conditional_node(node)
        ]
        
        for node_id in branching_nodes:
            node_type = nodes[node_id].get('type', '')
            
            if node_type in ['conditional', 'if_else']:
                paths = {'true': [], 'false': [], 'fallback': []}
            elif node_type in ['router', 'switch']:
                # Get expected paths from router configuration
                params = nodes[node_id].get('params', {})
                rules = params.get('rules', [])
                default_path = params.get('default_path', 'default')
                
                paths = {'fallback': []}
                for rule in rules:
                    if isinstance(rule, dict) and 'name' in rule:
                        paths[rule['name']] = []
                
                if default_path:
                    paths[default_path] = []
            elif node_type in ['parallel_fork', 'fork']:
                # Get expected paths from fork configuration
                params = nodes[node_id].get('params', {})
                branch_count = params.get('branch_count', 2)
                branch_names = params.get('branch_names', [])
                
                if not branch_names:
                    branch_names = [f"branch_{i+1}" for i in range(branch_count)]
                else:
                    branch_names = branch_names[:branch_count]
                
                paths = {'fallback': []}
                for branch_name in branch_names:
                    paths[branch_name] = []
            elif node_type in ['parallel_merge', 'merge']:
                # Merge nodes typically have simple paths
                paths = {'success': [], 'failed': [], 'partial': [], 'fallback': []}
            else:
                continue
            
            # Find outgoing edges
            outgoing_edges = [
                edge for edge in edges
                if (edge.get('source') == node_id or edge.get('from') == node_id)
            ]
            
            for edge in outgoing_edges:
                condition = edge.get('condition')
                target = edge.get('target') or edge.get('to')
                
                if not target:
                    continue
                
                if condition is None:
                    paths['fallback'].append(target)
                elif condition in paths:
                    paths[condition].append(target)
                else:
                    # Unknown path, add it
                    if condition not in paths:
                        paths[condition] = []
                    paths[condition].append(target)
            
            path_info[node_id] = paths
        
        return path_info


def patch_execution_engine():
    """
    Patch the existing execution engine to support conditional nodes.
    
    This function adds conditional support to the existing engine
    without modifying its core logic.
    """
    try:
        from ..services.enhanced_execution_engine import EnhancedExecutionEngine
        
        # Store original method
        original_get_node_input_items = EnhancedExecutionEngine._get_node_input_items
        
        def enhanced_get_node_input_items(self, node_id: str):
            """Enhanced version that handles conditional edges."""
            # Get standard input items
            items = original_get_node_input_items(self, node_id)
            
            # Find incoming edges to this node
            incoming_edges = [
                e for e in self.edges 
                if (e.get("to") or e.get("target")) == node_id
            ]
            
            # Process conditional edges
            filtered_items = []
            
            for edge in incoming_edges:
                source = edge.get("from") or edge.get("source")
                if not source:
                    continue
                
                source_items = self.node_output_items.get(source, [])
                edge_condition = edge.get('condition')
                
                # If no condition, include all items (standard behavior)
                if edge_condition is None:
                    filtered_items.extend(source_items)
                    continue
                
                # Check if source node is conditional
                source_node = self.nodes.get(source, {})
                if not ConditionalEngineExtension.is_conditional_node(source_node):
                    # Non-conditional source with condition - include all items
                    filtered_items.extend(source_items)
                    continue
                
                # Conditional source - check if condition matches
                for item in source_items:
                    item_data = item.get('json', {}) if isinstance(item, dict) else {}
                    condition_result = item_data.get('condition_result', {})
                    execution_path = condition_result.get('execution_path', 'true')
                    
                    if edge_condition == execution_path:
                        filtered_items.append(item)
            
            return filtered_items if filtered_items else items
        
        # Patch the method
        EnhancedExecutionEngine._get_node_input_items = enhanced_get_node_input_items
        
        logger.info("Successfully patched execution engine for conditional support")
        
    except ImportError as e:
        logger.warning(f"Could not patch execution engine: {e}")
    except Exception as e:
        logger.error(f"Error patching execution engine: {e}")


# Auto-patch when module is imported
patch_execution_engine()