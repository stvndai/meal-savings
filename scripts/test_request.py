import requests

files = [
    ("files", open("./flyers/flyer1.jpg", "rb")),
    ("files", open("./flyers/flyer2.jpg", "rb")),
    ("files", open("./flyers/flyer0.jpg", "rb")),
]
response = requests.post("http://localhost:8000/extract-and-match", files=files)
print(response.json())
