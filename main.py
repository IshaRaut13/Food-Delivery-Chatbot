from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
import db_helper
import generic_helper

app = FastAPI()

inprogress_orders = {}

@app.get("/favicon.ico")
async def favicon():
    return {}


@app.post("/")
async def handle_request(request: Request):
    # Retrieve the JSON data from the request
    payload = await request.json()
    print(f"Received Payload: {payload}")  # Debugging: Check entire payload

    # Extract the necessary information from the payload
    # based on the structure of the WebhookRequest from Dialogflow
    intent = payload['queryResult']['intent']['displayName']
    parameters = payload['queryResult']['parameters']
    output_contexts = payload['queryResult'].get('outputContexts', [])

    print(f"Extracted Intent: {intent}")  # Debugging: Check extracted intent
    print(f"Extracted Parameters: {parameters}")  # Debugging: Check parameters received

    #session_id = generic_helper.extract_session_id(output_contexts[0]["name"])
    # Extract session ID safely
    if output_contexts:
        session_id = generic_helper.extract_session_id(output_contexts[0]["name"])
        print(f"Extracted Session ID: {session_id}")  # Debugging: Check extracted session ID
    else:
        session_id = None
        print("No output contexts found!")

    intent_handler_dict = {
        'order.add - context: ongoing-order': add_to_order,
        'order.remove - context: ongoing-order': remove_from_order,
        'order.complete - context: ongoing-order': complete_order,
        'track.order': track_order
    }

    if intent not in intent_handler_dict:
        print(f"Intent not found: {intent}")
        return {"fulfillmentText": "Sorry, I couldn't understand your request."}

    return intent_handler_dict[intent](parameters, session_id)


def save_to_db(order: dict):
    next_order_id = db_helper.get_next_order_id()

    # Insert individual items along with quantity in orders table
    for food_item, quantity in order.items():
        rcode = db_helper.insert_order_item(
            food_item,
            quantity,
            next_order_id
        )

        if rcode == -1:
            return -1

    # Now insert order tracking status
    db_helper.insert_order_tracking(next_order_id, "in progress")

    return next_order_id


def complete_order(parameters: dict, session_id: str):
    if session_id not in inprogress_orders:
        fulfillment_text = "I'm having a trouble finding your order. Sorry! Can you place a new order please?"
    else:
        order = inprogress_orders[session_id]
        order_id = save_to_db(order)
        if order_id == -1:
            fulfillment_text = "Sorry, I couldn't process your order due to a backend error. " \
                               "Please place a new order again"
        else:
            order_total = db_helper.get_total_order_price(order_id)

            fulfillment_text = f"Awesome. We have placed your order. " \
                               f"Here is your order id # {order_id}. " \
                               f"Your order total is {order_total} which you can pay at the time of delivery!"

        del inprogress_orders[session_id]

    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })


def add_to_order(parameters: dict, session_id: str):
    food_items = parameters["food-item"]
    quantities = parameters["number"]

    if len(food_items) != len(quantities):
        fulfillment_text = "Sorry I didn't understand. Can you please specify food items and quantities clearly?"
    else:
        new_food_dict = dict(zip(food_items, quantities))

        if session_id in inprogress_orders:
            current_food_dict = inprogress_orders[session_id]
            current_food_dict.update(new_food_dict)
            inprogress_orders[session_id] = current_food_dict
        else:
            inprogress_orders[session_id] = new_food_dict

        order_str = generic_helper.get_str_from_food_dict(inprogress_orders[session_id])
        fulfillment_text = f"So far you have: {order_str}. Do you need anything else?"

    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })


def remove_from_order(parameters: dict, session_id: str):
    if session_id not in inprogress_orders:
        return JSONResponse(content={
            "fulfillmentText": "I'm having a trouble finding your order. Sorry! Can you place a new order please?"
        })

    food_items = parameters["food-item"]
    quantities = parameters.get("number", [1] * len(food_items))  # Default to 1 if no quantity specified
    current_order = inprogress_orders[session_id]

    removed_items = []
    no_such_items = []

    for item in food_items:
        if item not in current_order:
            no_such_items.append(item)
        else:
            removed_items.append(item)
            # del current_order[item]
            if current_order[item] > 1:  # Decrease quantity if more than 1
                current_order[item] -= 1
            else:  # Remove only if last one
                del current_order[item]

    if len(removed_items) > 0:
        fulfillment_text = f'Removed {",".join(removed_items)} from your order!'

    if len(no_such_items) > 0:
        fulfillment_text = f' Your current order does not have {",".join(no_such_items)}'

    if len(current_order.keys()) == 0:
        fulfillment_text += " Your order is empty!"
    else:
        order_str = generic_helper.get_str_from_food_dict(current_order)
        fulfillment_text += f" Here is what is left in your order: {order_str}"

    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })


# def remove_from_order(parameters: dict, session_id: str):
#     if session_id not in inprogress_orders:
#         return JSONResponse(content={
#             "fulfillmentText": "I'm having trouble finding your order. Sorry! Can you place a new order, please?"
#         })
#
#     food_items = parameters["food-item"]
#     quantities = parameters.get("number", [1] * len(food_items))  # Default to 1 if no quantity specified
#     current_order = inprogress_orders[session_id]
#
#     removed_items = []
#     no_such_items = []
#
#     for item, quantity in zip(food_items, quantities):  # Match each item with its quantity
#         if item not in current_order:
#             no_such_items.append(item)
#         else:
#             if current_order[item] > quantity:  # Reduce by the requested amount
#                 current_order[item] -= quantity
#                 removed_items.append(f"{quantity} {item}")
#             else:  # Remove completely if the quantity is equal or greater
#                 removed_items.append(f"{current_order[item]} {item}")
#                 del current_order[item]
#
#     fulfillment_text = ""
#
#     if removed_items:
#         fulfillment_text += f'Removed {", ".join(removed_items)} from your order!'
#
#     if no_such_items:
#         fulfillment_text += f' Your current order does not have {", ".join(no_such_items)}.'
#
#     if not current_order:  # Check if order is empty
#         fulfillment_text += " Your order is empty!"
#     else:
#         order_str = generic_helper.get_str_from_food_dict(current_order)
#         fulfillment_text += f" Here is what is left in your order: {order_str}"
#
#     return JSONResponse(content={
#         "fulfillmentText": fulfillment_text
#     })


# def remove_from_order(parameters: dict, session_id: str):
#     if session_id not in inprogress_orders:
#         return JSONResponse(content={
#             "fulfillmentText": "I'm having trouble finding your order. Sorry! Can you place a new order, please?"
#         })

#     food_items = parameters.get("food-item", [])  # Get food items list
#     quantities = parameters.get("number", [])  # Get quantities list

#     if not food_items:
#         return JSONResponse(content={
#             "fulfillmentText": "I couldn't find any items to remove. Please specify what to remove."
#         })

#     # # Ensure quantities list matches food_items list length
#     # if len(quantities) < len(food_items):
#     #     quantities.extend([1] * (len(food_items) - len(quantities)))  # Fill missing quantities with 1

#     # Ensure each food item has a corresponding quantity
#     corrected_quantities = [quantities[i] if i < len(quantities) else 1 for i in range(len(food_items))]

#     current_order = inprogress_orders[session_id]

#     removed_items = []
#     no_such_items = []

#     for item, quantity in zip(food_items, quantities):  # Match food items with their removal quantity
#         if item not in current_order:
#             no_such_items.append(item)
#         else:
#             if current_order[item] > quantity:  # Reduce by the requested quantity
#                 current_order[item] -= quantity
#                 removed_items.append(f"{quantity} {item}")
#             else:  # If requested quantity is equal or greater, remove completely
#                 removed_items.append(f"{current_order[item]} {item}")
#                 del current_order[item]

#     fulfillment_text = ""

#     if removed_items:
#         fulfillment_text += f'Removed {", ".join(removed_items)} from your order!'

#     if no_such_items:
#         fulfillment_text += f' Your current order does not have {", ".join(no_such_items)}.'

#     if not current_order:  # Check if order is empty
#         fulfillment_text += " Your order is empty!"
#     else:
#         order_str = generic_helper.get_str_from_food_dict(current_order)
#         fulfillment_text += f" Here is what is left in your order: {order_str}"

#     return JSONResponse(content={
#         "fulfillmentText": fulfillment_text
#     })




def track_order(parameters: dict, session_id: str):
    order_id = int(parameters.get('order_id'))

    print(f"Received order_id from Dialogflow: {order_id}")  # Debug print

    if not order_id:
        return JSONResponse(content={"fulfillmentText": "Please provide a valid order ID."})
    try:
        order_id = int(order_id)  # Convert to integer if needed
        print(f"Converted order_id: {order_id}")  # Debug print
    except ValueError:
        return JSONResponse(content={"fulfillmentText": "Invalid order ID format. Please enter a numeric order ID."})

    order_status = db_helper.get_order_status(order_id)

    print(f"Database returned order status: {order_status}")  # Debug print

    if order_status:
        fulfillment_text = f"The order status for order id: {order_id} is: {order_status}"
    else:
        fulfillment_text = f"No order found with order id: {order_id}"

    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })
