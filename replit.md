# Overview

This is a Chamber Logger API system that monitors and logs environmental data (temperature and humidity) from IoT sensors via MQTT communication. The system provides a FastAPI web service for accessing logged data and includes automatic archival functionality with Git integration for data persistence.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Framework
- **FastAPI** serves as the core web framework, providing REST API endpoints for data retrieval and file downloads
- **SQLAlchemy ORM** manages database operations with a declarative base model approach
- **SQLite database** stores chamber log entries locally in `chamber.db`

### Data Collection Architecture
- **MQTT client** subscribes to `chamber/log` topic on HiveMQ public broker for real-time sensor data
- **Asynchronous logging** system writes data every 60 seconds with timeout-based status tracking
- **Session-based monitoring** tracks chamber ON/OFF states with 60-second timeout threshold

### Data Storage Strategy
- **Primary storage**: SQLite database for active log queries and status monitoring
- **Archive system**: CSV file generation for historical data preservation in `archives/` folder
- **Git integration**: Automatic version control and remote backup of archive files

### API Design
- **RESTful endpoints** for log retrieval (`/logs`), status checking (`/status`), and archive management (`/archives`)
- **File serving capability** for CSV downloads via `/download/{filename}` endpoint
- **Dependency injection** pattern for database session management

### Time Management
- **Timezone-aware logging** with WIB (UTC+7) timezone handling
- **Timestamp tracking** for data freshness validation and session management

## External Dependencies

### MQTT Broker
- **HiveMQ Public Broker** (`broker.hivemq.com:1883`) for IoT device communication
- **Topic subscription**: `chamber/log` for sensor data ingestion

### Database
- **SQLite**: Local file-based database for log storage and querying
- **Schema**: Chamber logs with temperature/humidity readings from dual sensors

### Git Integration
- **GitHub repository** for archive file version control
- **SSH key authentication** via environment variable configuration
- **Automated commits** with timestamped messages for data archival

### Python Libraries
- **paho-mqtt**: MQTT client for IoT communication
- **FastAPI/Uvicorn**: Web framework and ASGI server
- **SQLAlchemy**: Database ORM and connection management