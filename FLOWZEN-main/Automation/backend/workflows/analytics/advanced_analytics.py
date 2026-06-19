"""
Advanced Analytics Engine
Predictive analytics, ML models, and business intelligence
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib
import logging

from ..models import Workflow, WorkflowExecution, WorkflowNode
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)

class PredictiveAnalytics:
    """
    Predictive analytics for workflow performance and optimization
    """
    
    def __init__(self):
        self.performance_monitor = PerformanceMonitor()
        self.models = {}
        self.scalers = {}
        self.model_cache_timeout = 3600  # 1 hour
        
    async def predict_workflow_performance(self, workflow_definition: Dict) -> Dict[str, Any]:
        """
        Predict workflow execution time, success rate, and resource usage
        """
        try:
            # Extract features from workflow definition
            features = self.extract_workflow_features(workflow_definition)
            
            # Get or train models
            execution_time_model = await self.get_execution_time_model()
            success_rate_model = await self.get_success_rate_model()
            resource_usage_model = await self.get_resource_usage_model()
            
            # Make predictions
            predictions = {
                'execution_time': await self.predict_execution_time(features, execution_time_model),
                'success_probability': await self.predict_success_rate(features, success_rate_model),
                'resource_usage': await self.predict_resource_usage(features, resource_usage_model),
                'bottlenecks': await self.identify_potential_bottlenecks(features),
                'optimization_suggestions': await self.generate_optimization_suggestions(features)
            }
            
            return {
                'success': True,
                'predictions': predictions,
                'confidence_scores': await self.calculate_confidence_scores(predictions),
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def extract_workflow_features(self, workflow_definition: Dict) -> np.ndarray:
        """Extract numerical features from workflow definition"""
        
        nodes = workflow_definition.get('nodes', [])
        edges = workflow_definition.get('edges', [])
        
        features = {
            # Basic structure features
            'node_count': len(nodes),
            'edge_count': len(edges),
            'complexity_score': len(nodes) * 2 + len(edges),
            
            # Node type distribution
            'trigger_nodes': sum(1 for node in nodes if node.get('type', '').startswith('trigger')),
            'action_nodes': sum(1 for node in nodes if node.get('type', '') in ['email', 'http_request', 'slack']),
            'logic_nodes': sum(1 for node in nodes if node.get('type', '') in ['condition', 'loop', 'delay']),
            'ai_nodes': sum(1 for node in nodes if node.get('type', '').startswith('ai')),
            
            # Complexity indicators
            'has_loops': int(any(node.get('type') == 'loop' for node in nodes)),
            'has_conditions': int(any(node.get('type') == 'condition' for node in nodes)),
            'has_error_handling': int(any('error' in str(node.get('config', {})) for node in nodes)),
            'has_delays': int(any(node.get('type') == 'delay' for node in nodes)),
            
            # External dependencies
            'external_apis': sum(1 for node in nodes if node.get('type') == 'http_request'),
            'email_actions': sum(1 for node in nodes if node.get('type') == 'email'),
            'database_operations': sum(1 for node in nodes if 'database' in node.get('type', '')),
            
            # Parallelization potential
            'parallel_branches': self.count_parallel_branches(nodes, edges),
            'sequential_depth': self.calculate_sequential_depth(nodes, edges),
            
            # Configuration complexity
            'avg_config_size': np.mean([len(str(node.get('config', {}))) for node in nodes]) if nodes else 0,
            'total_config_size': sum(len(str(node.get('config', {}))) for node in nodes),
        }
        
        return np.array(list(features.values())).reshape(1, -1)
    
    def count_parallel_branches(self, nodes: List[Dict], edges: List[Dict]) -> int:
        """Count potential parallel execution branches"""
        # Build adjacency list
        graph = {}
        for edge in edges:
            source = edge.get('source')
            target = edge.get('target')
            if source not in graph:
                graph[source] = []
            graph[source].append(target)
        
        # Count nodes with multiple outgoing edges
        parallel_points = sum(1 for node_id, targets in graph.items() if len(targets) > 1)
        return parallel_points
    
    def calculate_sequential_depth(self, nodes: List[Dict], edges: List[Dict]) -> int:
        """Calculate maximum sequential execution depth"""
        # Build adjacency list
        graph = {}
        in_degree = {}
        
        for node in nodes:
            node_id = node.get('id')
            graph[node_id] = []
            in_degree[node_id] = 0
        
        for edge in edges:
            source = edge.get('source')
            target = edge.get('target')
            if source in graph:
                graph[source].append(target)
                in_degree[target] = in_degree.get(target, 0) + 1
        
        # Find longest path using topological sort
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        depths = {node_id: 0 for node_id in in_degree}
        
        while queue:
            current = queue.pop(0)
            for neighbor in graph.get(current, []):
                depths[neighbor] = max(depths[neighbor], depths[current] + 1)
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return max(depths.values()) if depths else 0
    
    async def get_execution_time_model(self):
        """Get or train execution time prediction model"""
        if 'execution_time' not in self.models:
            await self.train_execution_time_model()
        return self.models['execution_time']
    
    async def get_success_rate_model(self):
        """Get or train success rate prediction model"""
        if 'success_rate' not in self.models:
            await self.train_success_rate_model()
        return self.models['success_rate']
    
    async def get_resource_usage_model(self):
        """Get or train resource usage prediction model"""
        if 'resource_usage' not in self.models:
            await self.train_resource_usage_model()
        return self.models['resource_usage']
    
    async def train_execution_time_model(self):
        """Train model to predict workflow execution time"""
        try:
            # Get training data
            training_data = await self.get_execution_training_data()
            
            if len(training_data) < 10:
                # Not enough data, use simple heuristic model
                self.models['execution_time'] = self.create_heuristic_time_model()
                return
            
            # Prepare features and targets
            X = np.array([data['features'] for data in training_data])
            y = np.array([data['execution_time'] for data in training_data])
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train model
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X_train_scaled, y_train)
            
            # Evaluate model
            train_score = model.score(X_train_scaled, y_train)
            test_score = model.score(X_test_scaled, y_test)
            
            logger.info(f"Execution time model trained - Train R²: {train_score:.3f}, Test R²: {test_score:.3f}")
            
            # Store model and scaler
            self.models['execution_time'] = model
            self.scalers['execution_time'] = scaler
            
        except Exception as e:
            logger.error(f"Error training execution time model: {e}")
            self.models['execution_time'] = self.create_heuristic_time_model()
    
    async def train_success_rate_model(self):
        """Train model to predict workflow success rate"""
        try:
            # Get training data
            training_data = await self.get_success_training_data()
            
            if len(training_data) < 10:
                self.models['success_rate'] = self.create_heuristic_success_model()
                return
            
            # Prepare features and targets
            X = np.array([data['features'] for data in training_data])
            y = np.array([data['success_rate'] for data in training_data])
            
            # Train model
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X_train_scaled, y_train)
            
            # Store model and scaler
            self.models['success_rate'] = model
            self.scalers['success_rate'] = scaler
            
        except Exception as e:
            logger.error(f"Error training success rate model: {e}")
            self.models['success_rate'] = self.create_heuristic_success_model()
    
    async def train_resource_usage_model(self):
        """Train model to predict resource usage"""
        try:
            # Get training data
            training_data = await self.get_resource_training_data()
            
            if len(training_data) < 10:
                self.models['resource_usage'] = self.create_heuristic_resource_model()
                return
            
            # Prepare and train model similar to above
            X = np.array([data['features'] for data in training_data])
            y = np.array([data['resource_usage'] for data in training_data])
            
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X_train_scaled, y_train)
            
            self.models['resource_usage'] = model
            self.scalers['resource_usage'] = scaler
            
        except Exception as e:
            logger.error(f"Error training resource usage model: {e}")
            self.models['resource_usage'] = self.create_heuristic_resource_model()
    
    async def get_execution_training_data(self) -> List[Dict]:
        """Get historical execution data for training"""
        # Get recent executions with performance data
        executions = WorkflowExecution.objects.filter(
            status='completed',
            completed_at__gte=timezone.now() - timedelta(days=30)
        ).select_related('workflow')[:1000]
        
        training_data = []
        for execution in executions:
            try:
                # Extract features from workflow definition
                features = self.extract_workflow_features(execution.workflow.definition)
                
                # Calculate execution time
                if execution.completed_at and execution.started_at:
                    execution_time = (execution.completed_at - execution.started_at).total_seconds()
                    
                    training_data.append({
                        'features': features.flatten(),
                        'execution_time': execution_time
                    })
            except Exception as e:
                logger.warning(f"Error processing execution {execution.id}: {e}")
                continue
        
        return training_data
    
    async def get_success_training_data(self) -> List[Dict]:
        """Get success rate training data"""
        # Group executions by workflow and calculate success rates
        workflows = Workflow.objects.annotate(
            total_executions=Count('executions'),
            successful_executions=Count('executions', filter=Q(executions__status='completed'))
        ).filter(total_executions__gte=5)
        
        training_data = []
        for workflow in workflows:
            try:
                features = self.extract_workflow_features(workflow.definition)
                success_rate = workflow.successful_executions / workflow.total_executions
                
                training_data.append({
                    'features': features.flatten(),
                    'success_rate': success_rate
                })
            except Exception as e:
                logger.warning(f"Error processing workflow {workflow.id}: {e}")
                continue
        
        return training_data
    
    async def get_resource_training_data(self) -> List[Dict]:
        """Get resource usage training data"""
        # This would require actual resource monitoring data
        # For now, return empty list to use heuristic model
        return []
    
    def create_heuristic_time_model(self):
        """Create simple heuristic model for execution time"""
        class HeuristicTimeModel:
            def predict(self, X):
                # Simple heuristic based on workflow complexity
                predictions = []
                for features in X:
                    node_count = features[0]
                    edge_count = features[1]
                    external_apis = features[10]
                    has_delays = features[7]
                    
                    # Base time + complexity factors
                    base_time = 5  # 5 seconds base
                    complexity_time = node_count * 2 + edge_count * 0.5
                    api_time = external_apis * 3  # 3 seconds per API call
                    delay_time = 10 if has_delays else 0
                    
                    total_time = base_time + complexity_time + api_time + delay_time
                    predictions.append(total_time)
                
                return np.array(predictions)
        
        return HeuristicTimeModel()
    
    def create_heuristic_success_model(self):
        """Create simple heuristic model for success rate"""
        class HeuristicSuccessModel:
            def predict(self, X):
                predictions = []
                for features in X:
                    external_apis = features[10]
                    has_error_handling = features[6]
                    complexity_score = features[2]
                    
                    # Base success rate
                    base_rate = 0.95
                    
                    # Reduce for external dependencies
                    api_penalty = external_apis * 0.02
                    
                    # Reduce for complexity
                    complexity_penalty = min(complexity_score * 0.001, 0.1)
                    
                    # Bonus for error handling
                    error_handling_bonus = 0.05 if has_error_handling else 0
                    
                    success_rate = base_rate - api_penalty - complexity_penalty + error_handling_bonus
                    success_rate = max(0.5, min(1.0, success_rate))  # Clamp between 0.5 and 1.0
                    
                    predictions.append(success_rate)
                
                return np.array(predictions)
        
        return HeuristicSuccessModel()
    
    def create_heuristic_resource_model(self):
        """Create simple heuristic model for resource usage"""
        class HeuristicResourceModel:
            def predict(self, X):
                predictions = []
                for features in X:
                    node_count = features[0]
                    ai_nodes = features[6]
                    database_ops = features[12]
                    
                    # Base resource usage (CPU percentage)
                    base_cpu = 10
                    node_cpu = node_count * 2
                    ai_cpu = ai_nodes * 15  # AI nodes are more resource intensive
                    db_cpu = database_ops * 5
                    
                    total_cpu = base_cpu + node_cpu + ai_cpu + db_cpu
                    total_cpu = min(total_cpu, 90)  # Cap at 90%
                    
                    predictions.append(total_cpu)
                
                return np.array(predictions)
        
        return HeuristicResourceModel()
    
    async def predict_execution_time(self, features: np.ndarray, model) -> float:
        """Predict workflow execution time"""
        if 'execution_time' in self.scalers:
            features_scaled = self.scalers['execution_time'].transform(features)
        else:
            features_scaled = features
        
        prediction = model.predict(features_scaled)[0]
        return max(1.0, float(prediction))  # Minimum 1 second
    
    async def predict_success_rate(self, features: np.ndarray, model) -> float:
        """Predict workflow success rate"""
        if 'success_rate' in self.scalers:
            features_scaled = self.scalers['success_rate'].transform(features)
        else:
            features_scaled = features
        
        prediction = model.predict(features_scaled)[0]
        return max(0.0, min(1.0, float(prediction)))  # Clamp between 0 and 1
    
    async def predict_resource_usage(self, features: np.ndarray, model) -> Dict[str, float]:
        """Predict workflow resource usage"""
        if 'resource_usage' in self.scalers:
            features_scaled = self.scalers['resource_usage'].transform(features)
        else:
            features_scaled = features
        
        cpu_prediction = model.predict(features_scaled)[0]
        
        # Estimate memory and network based on CPU
        memory_usage = cpu_prediction * 0.8  # Rough correlation
        network_usage = features[0][10] * 10  # Based on external API calls
        
        return {
            'cpu_percentage': max(5.0, min(95.0, float(cpu_prediction))),
            'memory_mb': max(50.0, float(memory_usage * 10)),
            'network_kb_per_sec': max(0.0, float(network_usage))
        }
    
    async def identify_potential_bottlenecks(self, features: np.ndarray) -> List[Dict[str, Any]]:
        """Identify potential performance bottlenecks"""
        bottlenecks = []
        feature_values = features[0]
        
        # Check for high complexity
        if feature_values[2] > 50:  # complexity_score
            bottlenecks.append({
                'type': 'high_complexity',
                'severity': 'medium',
                'description': 'Workflow has high complexity that may impact performance',
                'suggestion': 'Consider breaking into smaller workflows or optimizing node structure'
            })
        
        # Check for many external API calls
        if feature_values[10] > 5:  # external_apis
            bottlenecks.append({
                'type': 'external_dependencies',
                'severity': 'high',
                'description': 'Many external API calls may cause delays and failures',
                'suggestion': 'Add error handling, timeouts, and consider caching responses'
            })
        
        # Check for deep sequential chains
        if feature_values[14] > 10:  # sequential_depth
            bottlenecks.append({
                'type': 'sequential_processing',
                'severity': 'medium',
                'description': 'Long sequential chains limit parallelization',
                'suggestion': 'Look for opportunities to parallelize independent operations'
            })
        
        # Check for missing error handling
        if feature_values[6] == 0:  # has_error_handling
            bottlenecks.append({
                'type': 'no_error_handling',
                'severity': 'high',
                'description': 'Workflow lacks error handling mechanisms',
                'suggestion': 'Add condition nodes to handle potential errors and failures'
            })
        
        return bottlenecks
    
    async def generate_optimization_suggestions(self, features: np.ndarray) -> List[Dict[str, Any]]:
        """Generate optimization suggestions based on workflow analysis"""
        suggestions = []
        feature_values = features[0]
        
        # Parallelization opportunities
        if feature_values[13] > 0 and feature_values[14] > 5:  # parallel_branches and sequential_depth
            suggestions.append({
                'type': 'parallelization',
                'priority': 'high',
                'title': 'Optimize Parallel Execution',
                'description': 'Workflow has parallel branches that could be better utilized',
                'implementation': 'Restructure workflow to maximize parallel node execution',
                'estimated_improvement': '20-40% faster execution'
            })
        
        # Caching opportunities
        if feature_values[10] > 2:  # external_apis
            suggestions.append({
                'type': 'caching',
                'priority': 'medium',
                'title': 'Implement Response Caching',
                'description': 'Cache external API responses to reduce redundant calls',
                'implementation': 'Add caching nodes after API calls for frequently accessed data',
                'estimated_improvement': '15-30% faster execution, improved reliability'
            })
        
        # Error handling improvements
        if feature_values[6] == 0:  # has_error_handling
            suggestions.append({
                'type': 'error_handling',
                'priority': 'high',
                'title': 'Add Error Handling',
                'description': 'Implement comprehensive error handling and recovery',
                'implementation': 'Add condition nodes to check for errors and define fallback actions',
                'estimated_improvement': '10-20% higher success rate'
            })
        
        # Resource optimization
        if feature_values[5] > 3:  # ai_nodes
            suggestions.append({
                'type': 'resource_optimization',
                'priority': 'medium',
                'title': 'Optimize AI Node Usage',
                'description': 'AI nodes are resource-intensive and may benefit from optimization',
                'implementation': 'Batch AI operations or use more efficient models where possible',
                'estimated_improvement': '10-25% lower resource usage'
            })
        
        return suggestions
    
    async def calculate_confidence_scores(self, predictions: Dict[str, Any]) -> Dict[str, float]:
        """Calculate confidence scores for predictions"""
        # Simple confidence calculation based on model availability and data quality
        confidence_scores = {}
        
        # Base confidence depends on whether we have trained models
        base_confidence = 0.7 if 'execution_time' in self.models else 0.5
        
        confidence_scores['execution_time'] = base_confidence
        confidence_scores['success_probability'] = base_confidence
        confidence_scores['resource_usage'] = base_confidence * 0.8  # Lower confidence for resource predictions
        confidence_scores['bottlenecks'] = 0.8  # Rule-based, higher confidence
        confidence_scores['optimization_suggestions'] = 0.8  # Rule-based, higher confidence
        
        return confidence_scores

class AnomalyDetection:
    """
    Detect anomalies in workflow execution patterns
    """
    
    def __init__(self):
        self.isolation_forest = None
        self.feature_scaler = StandardScaler()
        self.trained = False
    
    async def detect_execution_anomalies(self, tenant_id: str, days: int = 7) -> Dict[str, Any]:
        """Detect anomalous workflow executions"""
        try:
            # Get recent executions
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            executions = WorkflowExecution.objects.filter(
                tenant_id=tenant_id,
                created_at__gte=start_date,
                created_at__lte=end_date
            ).select_related('workflow')
            
            if len(executions) < 10:
                return {
                    'success': True,
                    'anomalies': [],
                    'message': 'Insufficient data for anomaly detection'
                }
            
            # Extract features and detect anomalies
            features = self.extract_execution_features(executions)
            anomalies = await self.detect_anomalies(features, executions)
            
            return {
                'success': True,
                'anomalies': anomalies,
                'total_executions': len(executions),
                'anomaly_rate': len(anomalies) / len(executions),
                'detection_period': f'{days} days'
            }
            
        except Exception as e:
            logger.error(f"Anomaly detection error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def extract_execution_features(self, executions) -> np.ndarray:
        """Extract features from executions for anomaly detection"""
        features = []
        
        for execution in executions:
            try:
                # Calculate execution duration
                if execution.completed_at and execution.started_at:
                    duration = (execution.completed_at - execution.started_at).total_seconds()
                else:
                    duration = 0
                
                # Extract workflow complexity
                workflow_def = execution.workflow.definition
                nodes = workflow_def.get('nodes', [])
                edges = workflow_def.get('edges', [])
                
                feature_vector = [
                    duration,
                    len(nodes),
                    len(edges),
                    execution.created_at.hour,  # Hour of day
                    execution.created_at.weekday(),  # Day of week
                    1 if execution.status == 'completed' else 0,
                    len(str(execution.input_data)) if execution.input_data else 0,
                    len(str(execution.output_data)) if execution.output_data else 0,
                ]
                
                features.append(feature_vector)
                
            except Exception as e:
                logger.warning(f"Error extracting features for execution {execution.id}: {e}")
                continue
        
        return np.array(features)
    
    async def detect_anomalies(self, features: np.ndarray, executions) -> List[Dict[str, Any]]:
        """Detect anomalies using Isolation Forest"""
        if not self.trained:
            await self.train_anomaly_detector(features)
        
        # Scale features
        features_scaled = self.feature_scaler.transform(features)
        
        # Detect anomalies
        anomaly_scores = self.isolation_forest.decision_function(features_scaled)
        anomaly_labels = self.isolation_forest.predict(features_scaled)
        
        # Identify anomalous executions
        anomalies = []
        for i, (execution, score, label) in enumerate(zip(executions, anomaly_scores, anomaly_labels)):
            if label == -1:  # Anomaly
                anomaly_type = self.classify_anomaly_type(features[i], execution)
                
                anomalies.append({
                    'execution_id': str(execution.id),
                    'workflow_name': execution.workflow.name,
                    'anomaly_score': float(score),
                    'anomaly_type': anomaly_type,
                    'execution_time': execution.created_at.isoformat(),
                    'duration': features[i][0],
                    'status': execution.status,
                    'description': self.get_anomaly_description(anomaly_type, features[i])
                })
        
        return anomalies
    
    async def train_anomaly_detector(self, features: np.ndarray):
        """Train the anomaly detection model"""
        # Scale features
        features_scaled = self.feature_scaler.fit_transform(features)
        
        # Train Isolation Forest
        self.isolation_forest = IsolationForest(
            contamination=0.1,  # Expect 10% anomalies
            random_state=42,
            n_estimators=100
        )
        
        self.isolation_forest.fit(features_scaled)
        self.trained = True
    
    def classify_anomaly_type(self, features: np.ndarray, execution) -> str:
        """Classify the type of anomaly"""
        duration = features[0]
        node_count = features[1]
        status = execution.status
        
        # Classification rules
        if duration > 3600:  # More than 1 hour
            return 'long_execution'
        elif duration < 1 and node_count > 5:
            return 'unusually_fast'
        elif status != 'completed':
            return 'execution_failure'
        elif features[3] < 6 or features[3] > 22:  # Very early or late execution
            return 'unusual_timing'
        else:
            return 'pattern_deviation'
    
    def get_anomaly_description(self, anomaly_type: str, features: np.ndarray) -> str:
        """Get human-readable description of anomaly"""
        descriptions = {
            'long_execution': f'Execution took {features[0]:.1f} seconds, which is unusually long',
            'unusually_fast': f'Execution completed in {features[0]:.1f} seconds, which is unusually fast for {int(features[1])} nodes',
            'execution_failure': 'Execution failed when success was expected based on historical patterns',
            'unusual_timing': f'Execution occurred at {int(features[3])}:00, which is outside normal business hours',
            'pattern_deviation': 'Execution pattern deviates significantly from historical norms'
        }
        
        return descriptions.get(anomaly_type, 'Anomalous execution pattern detected')

# Global instances
predictive_analytics = PredictiveAnalytics()
anomaly_detection = AnomalyDetection()