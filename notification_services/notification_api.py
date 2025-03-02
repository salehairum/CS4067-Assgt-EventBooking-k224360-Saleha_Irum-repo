from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from flask_cors import CORS
from bson.objectid import ObjectId

app = Flask(__name__)

CORS(app, origins=["http://127.0.0.1:5500"])

# Configure MongoDB
app.config["MONGO_URI"] = "mongodb://localhost:27017/notification_service"
mongo = PyMongo(app)
notifications = mongo.db.notification  # Collection

# POST: Add a new notification
@app.route("/notifications", methods=["POST"])
def add_notification():
    data = request.json
    if not data or "booking_id" not in data or "user_id" not in data:
        return jsonify({"error": "Missing booking_id or user_id"}), 400

    notification_id = notifications.insert_one({
        "booking_id": data["booking_id"],
        "user_id": data["user_id"]
    }).inserted_id

    return jsonify({"message": "Notification added", "id": str(notification_id)}), 201

# GET: Retrieve all notifications (or filter by user_id)
@app.route("/notifications/<user_id>", methods=["GET"])
def get_notifications_by_user(user_id):
    # Find all notifications for the given user_id
    
    notifications_list = notifications.find({"user_id": user_id})

    # Convert MongoDB documents to JSON format
    result = [
        {"booking_id": n["booking_id"], "user_id": n["user_id"]}
        for n in notifications_list
    ]

    return jsonify(result), 200

@app.route("/notifications/<user_id>/count", methods=["GET"])
def get_notification_count(user_id):
    # Count the number of notifications for the given user_id
    count = notifications.count_documents({"user_id": user_id})

    # Return the count as a JSON response
    return jsonify({"notification_count": count}), 200

@app.route("/notifications/delete/<booking_id>", methods=["DELETE"])
def delete_notification(booking_id):
    # Attempt to delete the notification with the specified booking_id
    result = notifications.delete_one({"booking_id": booking_id})

    if result.deleted_count > 0:
        return jsonify({"message": "Notification deleted successfully"}), 200
    else:
        return jsonify({"error": "Notification not found"}), 404

if __name__ == "__main__":
    app.run(port=5001,debug=True)
