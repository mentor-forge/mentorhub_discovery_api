"""
Flask MongoDB API Server

Discovery API for the Mentor Hub system — the composite home Card list, the
typed `/api/cards/{type}` lists, the Notification control endpoints, and the
standard config, docs, and metrics endpoints.
"""

import sys
import os
import signal
from flask import Flask, send_from_directory

# Initialize Config Singleton (doesn't require external services)
from api_utils import Config

config = Config.get_instance()

# Initialize logging (Config constructor configures logging)
import logging

logger = logging.getLogger(__name__)
logger.info("============= Starting Server ===============")

# Initialize MongoIO Singleton and set enumerators and versions
from api_utils import MongoIO

mongo = MongoIO.get_instance()
config.set_enumerators(mongo.get_documents(config.ENUMERATORS_COLLECTION_NAME))
config.set_versions(mongo.get_documents(config.VERSIONS_COLLECTION_NAME))

# Initialize Flask App
from api_utils import MongoJSONEncoder

app = Flask(__name__)
app.json = MongoJSONEncoder(app)

# Route registration (all grouped together)
from api_utils import create_metric_routes, create_config_routes, create_explorer_routes
from api_utils import (
    create_notification_get_routes,
    create_path_get_routes,
    create_plan_get_routes,
    create_profile_get_routes,
    create_resource_get_routes,
)

from src.routes.card_routes import (
    create_cards_get_routes,
    create_customer_cards_get_routes,
    create_product_cards_get_routes,
    create_settings_cards_get_routes,
)
from src.routes.notification_routes import create_notification_routes
from src.services.notification_service import NotificationCardService
from src.services.path_service import PathCardService
from src.services.plan_service import PlanCardService
from src.services.profile_service import MemberCardService, MenteeCardService
from src.services.resource_service import ResourceCardService

# Register route blueprints
docs_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
app.register_blueprint(create_explorer_routes(docs_dir), url_prefix="/docs")
app.register_blueprint(create_config_routes(), url_prefix="/api/config")
app.register_blueprint(create_cards_get_routes(), url_prefix="/api/cards")

# Typed card lists: shared GET factories bound to Card-projecting subclasses,
# plus local blueprints for the sources with no shared service class.
app.register_blueprint(
    create_customer_cards_get_routes(), url_prefix="/api/cards/customer"
)
app.register_blueprint(
    create_product_cards_get_routes(), url_prefix="/api/cards/products"
)
app.register_blueprint(
    create_settings_cards_get_routes(), url_prefix="/api/cards/settings"
)
app.register_blueprint(
    create_resource_get_routes(ResourceCardService, name="resource_card_routes"),
    url_prefix="/api/cards/resources",
)
app.register_blueprint(
    create_path_get_routes(PathCardService, name="path_card_routes"),
    url_prefix="/api/cards/paths",
)
app.register_blueprint(
    create_plan_get_routes(PlanCardService, name="plan_card_routes"),
    url_prefix="/api/cards/plans",
)
app.register_blueprint(
    create_profile_get_routes(MemberCardService, name="member_card_routes"),
    url_prefix="/api/cards/members",
)
app.register_blueprint(
    create_profile_get_routes(MenteeCardService, name="mentee_card_routes"),
    url_prefix="/api/cards/mentees",
)
app.register_blueprint(
    create_notification_get_routes(
        NotificationCardService, name="notification_card_routes"
    ),
    url_prefix="/api/cards/notifications",
)

# Notification control: Discovery owns create, dismiss, and cancel. Bound to
# NotificationService so mutations return Notification documents, not Cards.
app.register_blueprint(create_notification_routes(), url_prefix="/api/notification")
metrics = create_metric_routes(app)  # This exposes /metrics endpoint

logger.info("============= Routes Registered ===============")
logger.info("  /api/cards - Composite home card list")
logger.info("  /api/cards/{type} - Typed card lists")
logger.info("  /api/notification - Notification create, dismiss, cancel")
logger.info("  /api/config - Configuration endpoint")
logger.info("  /docs - API Explorer")
logger.info("  /metrics - Prometheus metrics endpoint")

# Default discovery API port (architecture.yaml); override via API_PORT env in compose/dev.
DISCOVERY_API_PORT = 8397


# Define a signal handler for SIGTERM and SIGINT
def handle_exit(signum, frame):
    """Handle graceful shutdown on SIGTERM/SIGINT."""
    global mongo
    logger.info(f"Received signal {signum}. Initiating shutdown...")

    # Disconnect from MongoDB if connected
    if mongo is not None:
        logger.info("Closing MongoDB connection.")
        try:
            mongo.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting from MongoDB: {e}")

    logger.info("Shutdown complete.")
    sys.exit(0)


# Register the signal handler
signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

# Expose app for Gunicorn or direct execution
if __name__ == "__main__":
    api_port = int(os.environ.get("API_PORT", DISCOVERY_API_PORT))
    logger.info(f"Starting Flask server on port {api_port}")
    app.run(host="0.0.0.0", port=api_port, debug=False)
