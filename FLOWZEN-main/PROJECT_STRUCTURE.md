# FlowZen Project Structure Documentation

## Overview
FlowZen is a comprehensive workflow automation platform built with Django, designed to compete with tools like Zapier, n8n, and Make. It provides visual workflow building, trigger-based automation, and extensive third-party integrations.

## Architecture
- **Backend**: Django REST API with Celery for background task processing
- **Frontend**: HTML5/CSS3/JavaScript with Django templates
- **Database**: PostgreSQL for persistent storage
- **Task Queue**: Redis for Celery task brokering
- **Real-time**: Django Channels for WebSocket communication

## Directory Structure

### Root Level (`FLOWZEN-main/`)
```
├── Automation/              # Main application directory
├── docker/                  # Docker configuration files
├── docs/                    # Project documentation
├── scripts/                 # Utility scripts
├── screenshots/             # UI screenshots
├── docker-compose.yml       # Multi-container orchestration
├── Dockerfile              # Main Docker configuration
├── requirements.txt        # Python dependencies
└── README.md               # Comprehensive project documentation
```

### Main Application (`Automation/`)

#### Backend (`Automation/backend/`)
```
├── project/                # Django project configuration
│   ├── settings.py         # Main Django settings
│   ├── urls.py            # Root URL configuration
│   ├── wsgi.py            # WSGI application entry point
│   └── asgi.py            # ASGI application for WebSockets
├── workflows/              # Core workflow automation logic
│   ├── models.py          # Database models for workflows, nodes, executions
│   ├── views.py           # API endpoints and view logic
│   ├── actions.py         # Action node implementations
│   ├── tasks.py           # Celery task definitions
│   ├── nodes/             # Individual node implementations
│   ├── triggers/          # Trigger system implementations
│   ├── ai/                # AI integration components
│   ├── email/             # Email automation modules
│   ├── execution/         # Workflow execution engine
│   └── api/               # REST API serializers and views
├── authentication/        # User authentication and authorization
├── credentials_storage/   # Encrypted credential management
├── notifications/         # Notification system
├── utils/                 # Utility functions and helpers
└── manage.py              # Django management script
```

#### Frontend (`Automation/frontend/`)
```
├── templates/             # Django HTML templates
│   ├── base.html         # Base template structure
│   ├── dashboard/        # Dashboard pages
│   ├── workflows/        # Workflow management UI
│   └── user/             # User account pages
├── css/                  # Stylesheets
├── js/                   # JavaScript functionality
└── static/               # Static assets
```

## Core Components

### Workflow Engine (`workflows/`)
- **Models**: Defines Workflow, Node, Execution, and related data structures
- **Actions**: Implements various action nodes (HTTP requests, database operations, etc.)
- **Triggers**: Handles trigger mechanisms (webhooks, schedules, events)
- **Execution**: Manages workflow execution state and node processing
- **AI Integration**: Provides AI-powered workflow capabilities

### Node System (`workflows/nodes/`)
Contains individual node implementations for different integrations:
- HTTP request nodes
- Database operation nodes
- Email nodes (Gmail, SMTP)
- Communication nodes (Telegram, WhatsApp)
- AI/LLM integration nodes
- Data transformation nodes

### Task Processing
- **Celery Workers**: Execute workflow nodes asynchronously
- **Beat Scheduler**: Handles time-based triggers
- **Redis**: Task queue broker and caching

### Security Features
- Encrypted credential storage
- OAuth integration handling
- Permission-based access control
- Input validation and sanitization

## Key Files

### Configuration
- `project/settings.py` - Main Django configuration
- `docker-compose.yml` - Container orchestration
- `requirements.txt` - Python dependencies

### Core Logic
- `workflows/models.py` - Data models (69KB)
- `workflows/views.py` - API endpoints (152KB)
- `workflows/actions.py` - Action implementations (45KB)
- `workflows/tasks.py` - Celery tasks (38KB)

### AI Integration
- `workflows/ai_assistant_api.py` - AI assistant functionality (40KB)
- `workflows/ai_services.py` - AI service integrations (14KB)

## Deployment Structure
- Docker-based deployment with multiple containers
- Separate containers for: web server, database, Redis, Celery workers
- Environment-based configuration management
- Production-ready settings included

## Integration Capabilities
- REST API integrations
- Database connections (PostgreSQL, SQLite)
- Email services (Gmail, SMTP)
- Messaging platforms (Telegram, WhatsApp)
- AI/LLM services
- Custom HTTP endpoints

## Development Features
- Comprehensive logging and debugging
- Real-time execution monitoring via WebSockets
- Visual workflow builder interface
- Extensible node system for custom integrations
- Automated testing framework

This structure provides a solid foundation for a scalable, enterprise-ready workflow automation platform with extensive customization capabilities.
