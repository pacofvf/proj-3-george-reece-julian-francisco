#!/usr/bin/env python
import json
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ValidationError
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
from flask import Flask, request

app = Flask(__name__)
app.producer = None


def log_to_kafka(topic, event):
    if app.producer is None:
        try:
            app.producer = KafkaProducer(bootstrap_servers='kafka:29092')
        except NoBrokersAvailable:
            if app.debug:
                print('NoBrokersAvailable')
                return
            raise NoBrokersAvailable
    event.update(request.headers)
    app.producer.send(topic, json.dumps(event).encode())


@app.route("/")
def default_response():
    default_event = {'event_type': 'default'}
    log_to_kafka('events', default_event)
    return "This is the default response!\n"


# Basic Event Schema

@app.route("/purchase_a_sword")
def purchase_a_sword():
    purchase_sword_event = {'event_type': 'purchase_sword'}
    log_to_kafka('events', purchase_sword_event)
    return "Sword Purchased!\n"


@app.route("/purchase_a_knife")
def purchase_a_knife():
    purchase_knife_event = {'event_type': 'purchase_knife',
                            'description': 'very sharp knife'}
    log_to_kafka('events', purchase_knife_event)
    return "Knife Purchased!\n"


@app.route("/join-a-guild")
def join_a_guild():
    join_guild_event = {"event_type": "join_guild",
                        "description": "join a guild"}
    log_to_kafka('events', join_guild_event)
    return "Guild Joined!\n"


# New Schema Format

@app.route("/", methods=['GET', 'POST'])
def home():
    if request.method == 'GET':
        default_event = {'event_type': 'default'}
        log_to_kafka('events', default_event)
        return "This is the default response!\n"


# Store Interactions

# class Purchase(BaseModel):
#     request_id: int
#     user_id: int
#     item_id: int
#     item_kind: Optional[str] = None
#     item_type: Optional[str] = None
#     quantity: int
#     price_paid: float
#     vendor_id: int
#     vendor_quantity_avail: Optional[int] = None
#     vendor_list_price: Optional[float] = None
#     client_timestamp: Optional[datetime] = None
#     request_status = "failed"


class PurchaseEvent(BaseModel):
    user_id: Optional[int] = None
    item_id: Optional[int] = None
    quantity: Optional[int] = None
    price_paid: Optional[float] = None
    vendor_id: Optional[int] = None
    api_string: Optional[str]
    request_status: Optional[str]


@app.route("/purchase", methods=['POST'])
def purchase():
    # Normal behavior first
    try:
        # Validate JSON and copy if works, need to replace with proper inputs
        content = request.get_json(silent=True)
        purchase_event = PurchaseEvent(**content)
        purchase_event.api_string = json.dumps(content)  # replace w full str
        purchase_event.request_status = 'success'
    # If data missing required fields, log request and errors
    except ValidationError as e:
        # we need to get the json data again to keep the linter happy.
        content = request.get_json(silent=True)
        purchase_event = PurchaseEvent(**{
            "request_status": "invalid",
            "api_string": json.dumps(content)
        })
    purchase_event = purchase_event.dict()
    log_to_kafka("purchases", purchase_event)
    return purchase_event


# TO DO:
#   1. Determine and implement correct input path
#   2. Add GET method


# Guild Interactions

class GuildAction(BaseModel):
    request_id: int
    user_id: int
    guild_id: int
    action: Optional[str] = None
    client_timestamp: Optional[datetime] = None
    request_status = "failed"


class GuildActionEvent(GuildAction):
    user_id: Optional[int] = None
    guild_id: Optional[int] = None
    addl_data: Optional[str] = None
    api_string: str


@app.route("/guild", methods=['POST'])
def guild_action(guild_action_details):
    # Normal behavior first
    try:
        # Validate JSON and copy if works, need to replace with proper inputs
        GuildAction(**guild_action_details)
        guild_action = dict(guild_action_details)  # May not be necessary in API context
        guild_action["api_string"] = json.dumps(guild_action_details)  # replace w full str
        # Force into full schema and add additional fields to JSON blob
        guild_action_event = GuildActionEvent(**purchase).__dict__
        addl_data = {}
        for k, v in guild_action_details.items():
            if k not in guild_action_event.keys():
                addl_data[k] = v
        guild_action_event["addl_data"] = addl_data
    # If data missing required fields, log request and errors
    except ValidationError as e:
        guild_action_event = GuildActionEvent(**{
            "request_id": guild_action_details["request_id"],
            "request_status": "invalid",
            "addl_data": json.dumps(json.loads(e.json())),
            "api_string": json.dumps(guild_action_details)
        }).__dict__
    log_to_kafka("guild_actions", guild_action_event)
    return f"""{guild_action_event["request_id"]}: {guild_action_event["request_status"]}"""


# TO DO:
#   1. Determine and implement correct input path
#   2. Add GET method

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
