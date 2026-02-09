from django.core.exceptions import PermissionDenied

class ProductionRouter:
    """
    A router to control all database operations on models in the
    produccion application.
    """
    route_app_labels = {'produccion'}

    def db_for_read(self, model, **hints):
        """
        Attempts to read produccion models go to production.
        """
        if model._meta.app_label in self.route_app_labels:
            return 'production'
        return None

    def db_for_write(self, model, **hints):
        """
        Attempts to write produccion models go to production.
        """
        if model._meta.app_label in self.route_app_labels:
            # Explicitly block writes to this database
            raise PermissionDenied("Writing to the production database is strictly forbidden.")
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if a model in the produccion app is involved.
        """
        if (
            obj1._meta.app_label in self.route_app_labels or
            obj2._meta.app_label in self.route_app_labels
        ):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Make sure the produccion app only appears in the
        'production' database.
        """
        if app_label in self.route_app_labels:
            return False # Never migrate this app (it's legacy)
        return None
