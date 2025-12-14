# Real Estate Web Scraper (Rightmove)

## 📌 Project Overview
This project is a Python web scraping tool built with **Scrapy** to collect real estate property listings from **Rightmove**.  
It extracts structured data such as price, location, property type, area, features, images, and video tour availability.

---

## 🎯 Key Features
- Scrapes property listings in London
- Supports pagination and large-scale crawling
- Extracts:
  - Property type
  - Price
  - Location
  - Area, beds, and baths
  - Property features and description
  - Images and video tour links
- Saves data in JSON Lines (`.jsonl`) format
- Includes basic anti-bot protections (delays and throttling)

---

## 🛠 Technologies Used
- Python
- Scrapy
- Regular Expressions
- JSONL data format

---

## 📂 Output
The scraped data is saved as:
real_estate_properties.jsonl
