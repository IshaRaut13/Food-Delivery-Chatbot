import re

def get_str_from_food_dict(food_dict: dict):
    result = ", ".join([f"{int(value)} {key}" for key, value in food_dict.items()])
    return result


def extract_session_id(session_str: str):
    match = re.search(r"/sessions/(.*?)/contexts/", session_str)
    if not match:
        print("❌ No session ID found in context name!")
        return None
    extracted_string = match.group(1)
    print(f"✅ Extracted session ID: {extracted_string}")  # Debug print

    return extracted_string
    # else:
    #     return "ERROR"
