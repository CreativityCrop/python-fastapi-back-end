import json
import time

import lorem
import random
import requests

API_URL = "http://creativitycrop.tech:8000/api"
login_data = {
    "username": "ivanka",
    "pass_hash": "parola"
}


def generate_ideas_and_post(token, count):
    for i in (1, count):
        print("Creating idea #" + i.__str__())
        title = lorem.sentence()
        short_desc = lorem.paragraph()
        long_desc = lorem.text()
        categories = lorem.text()[0:25].split(" ")
        price = random.randint(15, 250)

        body = {
            "title": title,
            "short_desc": short_desc,
            "long_desc": long_desc,
            "categories": categories,
            "price": price
        }

        try:
            requests.post(
                API_URL + "/ideas/post",
                data=json.dumps(body),
                headers={
                    "Token": token,
                    "Content-Type": "application/json"
                }
            )
        except Exception as ex:
            print(ex.__str__())
            return
        print("Idea #" + i.__str__() + " posted!")
        time.sleep(2)


if __name__ == "__main__":
    r = requests.post(
        API_URL + "/auth/login",
        data=json.dumps(login_data),
        headers={
            "Content-Type": "application/json"
        }
    )

    result = json.loads(r.content)["accessToken"]
    generate_ideas_and_post(result, 2)
