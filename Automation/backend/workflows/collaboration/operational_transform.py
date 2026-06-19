"""
Operational Transform for Real-time Collaboration
Handles conflict resolution and operation transformation
"""

import json
from typing import Dict, List, Any, Tuple
from django.utils import timezone
from .models import WorkflowOperation, ConflictResolution

class OperationalTransform:
    """
    Operational Transform implementation for workflow collaboration
    Ensures consistency across concurrent edits
    """
    
    def __init__(self):
        self.transform_functions = {
            ('node_add', 'node_add'): self.transform_node_add_node_add,
            ('node_add', 'node_edit'): self.transform_node_add_node_edit,
            ('node_add', 'node_delete'): self.transform_node_add_node_delete,
            ('node_edit', 'node_edit'): self.transform_node_edit_node_edit,
            ('node_edit', 'node_delete'): self.transform_node_edit_node_delete,
            ('node_delete', 'node_delete'): self.transform_node_delete_node_delete,
            ('edge_add', 'edge_add'): self.transform_edge_add_edge_add,
            ('edge_add', 'node_delete'): self.transform_edge_add_node_delete,
            ('edge_edit', 'edge_edit'): self.transform_edge_edit_edge_edit,
        }
    
    async def transform_operation(self, operation: WorkflowOperation, session_id: str) -> Dict[str, Any]:
        """
        Transform operation against concurrent operations
        """
        # Get concurrent operations
        concurrent_ops = await self.get_concurrent_operations(operation, session_id)
        
        # Apply transformations
        transformed_op = operation
        for concurrent_op in concurrent_ops:
            transformed_op = await self.transform_against_operation(transformed_op, concurrent_op)
        
        # Update vector clock
        transformed_op.vector_clock = await self.update_vector_clock(
            transformed_op.vector_clock, 
            operation.participant_id
        )
        
        return self.serialize_operation(transformed_op)
    
    async def transform_against_operation(self, op1: WorkflowOperation, op2: WorkflowOperation) -> WorkflowOperation:
        """Transform op1 against op2"""
        
        # Get transform function
        transform_key = (op1.operation_type, op2.operation_type)
        transform_func = self.transform_functions.get(transform_key)
        
        if transform_func:
            return await transform_func(op1, op2)
        else:
            # Default: no transformation needed
            return op1
    
    # Transform functions for different operation pairs
    
    async def transform_node_add_node_add(self, op1: WorkflowOperation, op2: WorkflowOperation) -> WorkflowOperation:
        """Transform node addition against another node addition"""
        
        # Check if adding nodes at same position
        pos1 = op1.operation_data.get('position', {})
        pos2 = op2.operation_data.get('position', {})
        
        if self.positions_overlap(pos1, pos2):
            # Offset position to avoid overlap
            op1.operation_data['position'] = self.offset_position(pos1, 50, 50)
        
        return op1
    
    async def transform_node_add_node_edit(self, op1: WorkflowOperation, op2: WorkflowOperation) -> WorkflowOperation:
        """Transform node addition against node edit"""
        # No conflict - different operations
        return op1
    
    async def transform_node_add_node_delete(self, op1: WorkflowOperation, op2: WorkflowOperation) -> WorkflowOperation:
        """Transform node addition against node deletion"""
        # Check if adding node with same ID as deleted node
        if op1.target_id == op2.target_id:
            # Generate new ID for the added node
            op1.target_id = self.generate_new_node_id()
            op1.operation_data['id'] = op1.target_id
        
        return op1
    
    async def transform_node_edit_node_edit(self, op1: WorkflowOperation, op2: WorkflowOperation) -> WorkflowOperation:
        """Transform node edit against another node edit"""
        
        if op1.target_id != op2.target_id:
            # Different nodes - no conflict
            return op1
        
        # Same node - merge changes
        merged_data = self.merge_node_changes(
            op1.operation_data.get('changes', {}),
            op2.operation_data.get('changes', {})
        )
        
        op1.operation_data['changes'] = merged_data
        
        # Record conflict for manual resolution if needed
        if self.has_conflicting_changes(op1.operation_data, op2.operation_data):
            await self.record_conflict(op1, op2, 'manual_merge')
        
        return op1
    
    async def transform_node_edit_node_delete(self, op1: WorkflowOperation, op2: WorkflowOperation) -> WorkflowOperation:
        """Transform node edit against node deletion"""
        
        if op1.target_id == op2.target_id:
            # Editing deleted node - cancel edit
            op1.operation_data['cancelled'] = True
            op1.operation_data['reason'] = 'Node was deleted'
        
        return op1
    
    async def transform_node_delete_node_delete(self, op1: WorkflowOperation, op2: WorkflowOperation) -> WorkflowOperation:
        """Transform node deletion against another node deletion"""
        
        if op1.target_id == op2.target_id:
            # Deleting same node - cancel one operation
            if op1.timestamp > op2.timestamp:
                op1.operation_data['cancelled'] = True
                op1.operation_data['reason'] = 'Node already deleted'
        
        return op1
    
    async def transform_edge_add_edge_add(self, op1: WorkflowOperation, op2: WorkflowOperation) -> WorkflowOperation:
        """Transform edge addition against another edge addition"""
        
        # Check if adding same edge
        edge1 = op1.operation_data
        edge2 = op2.operation_data
        
        if (edge1.get('source') == edge2.get('source') and 
            edge1.get('target') == edge2.get('target')):
            # Same edge - cancel duplicate
            op1.operation_data['cancelled'] = True
            op1.operation_data['reason'] = 'Duplicate edge'
        
        return op1
    
    async def transform_edge_add_node_delete(self, op1: WorkflowOperation, op2: WorkflowOperation) -> WorkflowOperation:
        """Transform edge addition against node deletion"""
        
        edge_data = op1.operation_data
        deleted_node_id = op2.target_id
        
        # Check if edge connects to deleted node
        if (edge_data.get('source') == deleted_node_id or 
            edge_data.get('target') == deleted_node_id):
            # Cancel edge addition
            op1.operation_data['cancelled'] = True
            op1.operation_data['reason'] = 'Connected node was deleted'
        
        return op1
    
    async def transform_edge_edit_edge_edit(self, op1: WorkflowOperation, op2: WorkflowOperation) -> WorkflowOperation:
        """Transform edge edit against another edge edit"""
        
        if op1.target_id != op2.target_id:
            # Different edges - no conflict
            return op1
        
        # Same edge - merge changes
        merged_data = self.merge_edge_changes(
            op1.operation_data.get('changes', {}),
            op2.operation_data.get('changes', {})
        )
        
        op1.operation_data['changes'] = merged_data
        return op1
    
    # Helper methods
    
    def positions_overlap(self, pos1: Dict, pos2: Dict) -> bool:
        """Check if two positions overlap"""
        x1, y1 = pos1.get('x', 0), pos1.get('y', 0)
        x2, y2 = pos2.get('x', 0), pos2.get('y', 0)
        
        # Consider overlap if within 100px
        return abs(x1 - x2) < 100 and abs(y1 - y2) < 100
    
    def offset_position(self, position: Dict, offset_x: int, offset_y: int) -> Dict:
        """Offset position by given amounts"""
        return {
            'x': position.get('x', 0) + offset_x,
            'y': position.get('y', 0) + offset_y
        }
    
    def generate_new_node_id(self) -> str:
        """Generate new unique node ID"""
        import uuid
        return f"node_{uuid.uuid4().hex[:8]}"
    
    def merge_node_changes(self, changes1: Dict, changes2: Dict) -> Dict:
        """Merge node changes with conflict resolution"""
        merged = changes1.copy()
        
        for key, value in changes2.items():
            if key in merged:
                # Conflict - use last write wins for now
                # TODO: Implement more sophisticated merging
                merged[key] = value
            else:
                merged[key] = value
        
        return merged
    
    def merge_edge_changes(self, changes1: Dict, changes2: Dict) -> Dict:
        """Merge edge changes"""
        merged = changes1.copy()
        merged.update(changes2)
        return merged
    
    def has_conflicting_changes(self, data1: Dict, data2: Dict) -> bool:
        """Check if two operations have conflicting changes"""
        changes1 = data1.get('changes', {})
        changes2 = data2.get('changes', {})
        
        # Check for overlapping keys with different values
        for key in changes1:
            if key in changes2 and changes1[key] != changes2[key]:
                return True
        
        return False
    
    async def get_concurrent_operations(self, operation: WorkflowOperation, session_id: str) -> List[WorkflowOperation]:
        """Get operations that happened concurrently"""
        from django.db import models
        
        # Get operations from same session that happened around the same time
        time_window = timezone.timedelta(seconds=5)  # 5 second window
        
        concurrent_ops = WorkflowOperation.objects.filter(
            session_id=session_id,
            timestamp__gte=operation.timestamp - time_window,
            timestamp__lte=operation.timestamp + time_window
        ).exclude(id=operation.id)
        
        return list(concurrent_ops)
    
    async def update_vector_clock(self, vector_clock: Dict, participant_id: str) -> Dict:
        """Update vector clock for operation"""
        if not vector_clock:
            vector_clock = {}
        
        # Increment clock for this participant
        vector_clock[str(participant_id)] = vector_clock.get(str(participant_id), 0) + 1
        
        return vector_clock
    
    async def record_conflict(self, op1: WorkflowOperation, op2: WorkflowOperation, strategy: str):
        """Record conflict for manual resolution"""
        from django.contrib.auth.models import User
        
        # For now, use system user for automatic conflicts
        system_user = User.objects.get(username='system')
        
        ConflictResolution.objects.create(
            session_id=op1.session_id,
            operation_a=op1,
            operation_b=op2,
            resolution_strategy=strategy,
            resolved_by=system_user,
            resolution_data={
                'automatic': True,
                'strategy_used': strategy
            },
            final_state=op1.operation_data
        )
    
    def serialize_operation(self, operation: WorkflowOperation) -> Dict[str, Any]:
        """Serialize operation for transmission"""
        return {
            'id': str(operation.id),
            'type': operation.operation_type,
            'target_id': operation.target_id,
            'data': operation.operation_data,
            'vector_clock': operation.vector_clock,
            'timestamp': operation.timestamp.isoformat(),
            'participant_id': str(operation.participant_id)
        }