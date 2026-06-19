from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
import io
import base64
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate
from ..models import WorkflowExecution

import matplotlib
matplotlib.use('Agg') # Non-interactive backend
import matplotlib.pyplot as plt

class ExecutionAnalyticsView(APIView):
    """
    Generate a graph of workflow executions over the last 7 days.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Data Gathering
            end_date = timezone.now()
            start_date = end_date - timedelta(days=7)
            
            # Query: Count executions per day for this user's workflows
            data = (
                WorkflowExecution.objects
                .filter(
                    workflow__owner=request.user,
                    created_at__range=(start_date, end_date)
                )
                .annotate(date=TruncDate('created_at'))
                .values('date')
                .annotate(count=Count('id'))
                .order_by('date')
            )
            
            # Transform to lists for plotting
            dates_dict = {item['date']: item['count'] for item in data}
            plot_dates = []
            plot_counts = []
            
            current = start_date.date()
            for _ in range(8): # 0 to 7 days
                plot_dates.append(current.strftime('%m-%d'))
                plot_counts.append(dates_dict.get(current, 0))
                current += timedelta(days=1)

            # Plotting
            plt.figure(figsize=(10, 4), dpi=100)
            plt.style.use('dark_background')
            
            # Bar Chart
            bars = plt.bar(plot_dates, plot_counts, color='#6366f1', alpha=0.7)
            
            # Styling
            plt.title('Workflow Executions (Last 7 Days)', color='white', pad=20)
            plt.xlabel('Date', color='#cbd5e1')
            plt.ylabel('Runs', color='#cbd5e1')
            plt.grid(axis='y', linestyle='--', alpha=0.2)
            plt.box(False)
            
            # Hide ticks but keep labels
            plt.tick_params(axis='both', which='both', length=0, colors='#94a3b8')
            
            # Add values on top of bars
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    plt.text(bar.get_x() + bar.get_width()/2., height,
                             f'{height}',
                             ha='center', va='bottom', color='white')

            # Save to Buffer
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', transparent=True, bbox_inches='tight')
            plt.close()
            buffer.seek(0)
            
            # Encode
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            return Response({
                'success': True,
                'image': f"data:image/png;base64,{image_base64}",
                'stats': {
                    'total_last_7_days': sum(plot_counts),
                    'average_daily': round(sum(plot_counts) / 7, 1)
                }
            })
            
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=500)
