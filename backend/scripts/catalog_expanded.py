"""Additional deterministic demo catalog entries for QuickBite.

These entries are generated from curated cuisine/dish templates so the catalog
can grow without hand-maintaining hundreds of rows. Seeding remains idempotent
because restaurants are upserted by name and menu items by restaurant/name.
"""

from __future__ import annotations

import random

_CUISINES = [
    ("North Indian", "Tandoor", [
        ("Paneer Tikka", "Smoky cottage cheese with peppers", 23900),
        ("Dal Tadka", "Yellow lentils tempered with garlic", 15900),
        ("Chicken Curry", "Home-style chicken curry", 27900),
        ("Jeera Aloo", "Cumin potatoes", 12900),
        ("Butter Naan", "Soft tandoor naan", 6900),
        ("Gajar Halwa", "Warm carrot pudding", 9900),
        ("Veg Pulao", "Fragrant basmati with vegetables", 17900),
        ("Mutton Rogan Josh", "Kashmiri spiced mutton", 34900),
        ("Palak Corn", "Spinach with sweet corn", 18900),
        ("Lassi", "Chilled yogurt drink", 5900),
        ("Gulab Jamun", "Soft milk dumplings in syrup", 8900),
        ("Papad Basket", "Roasted papads with chutney", 4900),
        ("Shahi Paneer", "Cottage cheese in rich gravy", 25900),
    ]),
    ("South Indian", "Udupi", [
        ("Masala Dosa", "Crisp dosa with spiced potato", 12900),
        ("Idli Sambar", "Steamed rice cakes with sambar", 8900),
        ("Medu Vada", "Crispy lentil fritters", 9900),
        ("Uttapam", "Thick rice pancake with toppings", 13900),
        ("Filter Coffee", "South Indian filter coffee", 5900),
        ("Lemon Rice", "Tangy tempered rice", 11900),
        ("Curd Rice", "Cooling yogurt rice", 10900),
        ("Rava Dosa", "Semolina crisp dosa", 14900),
        ("Pongal", "Pepper cumin rice", 11900),
        ("Coconut Chutney", "Fresh coconut chutney", 3900),
        ("Mysore Pak", "Ghee-rich gram flour sweet", 9900),
        ("Rasam", "Spicy tamarind soup", 7900),
        ("Bisi Bele Bath", "Lentil rice with vegetables", 15900),
    ]),
    ("Bengali", "Bhoj", [
        ("Fish Curry", "Bengali fish in mustard gravy", 28900),
        ("Mishti Doi", "Sweet yogurt", 7900),
        ("Luchi", "Puffed fried bread", 8900),
        ("Aloo Posto", "Potato with poppy seeds", 14900),
        ("Cholar Dal", "Bengal gram with coconut", 13900),
        ("Rosogolla", "Spongy syrup dessert", 8900),
        ("Prawn Malai Curry", "Prawns in coconut gravy", 34900),
        ("Kosha Mangsho", "Slow-cooked mutton", 36900),
        ("Begun Bhaja", "Fried eggplant slices", 9900),
        ("Khichuri", "Rice and lentil comfort dish", 15900),
        ("Sandesh", "Fresh chhena sweet", 9900),
        ("Payesh", "Rice pudding", 8900),
        ("Macher Jhol", "Light fish stew", 26900),
    ]),
    ("Chinese", "Wok", [
        ("Veg Manchurian", "Fried vegetable balls in sauce", 18900),
        ("Hakka Noodles", "Stir-fried noodles", 17900),
        ("Fried Rice", "Wok-tossed rice", 16900),
        ("Chilli Paneer", "Spicy paneer cubes", 20900),
        ("Spring Rolls", "Crispy vegetable rolls", 12900),
        ("Hot and Sour Soup", "Tangy spicy soup", 9900),
        ("Kung Pao Chicken", "Chicken with peanuts", 24900),
        ("Dim Sums", "Steamed dumplings", 15900),
        ("Schezwan Rice", "Spicy schezwan fried rice", 18900),
        ("Chilli Chicken", "Dry chilli chicken", 23900),
        ("Manchow Soup", "Crispy noodle soup", 10900),
        ("Honey Chilli Potato", "Crispy potatoes in honey chilli", 14900),
        ("American Chopsuey", "Crispy noodles with sauce", 19900),
    ]),
    ("Italian", "Pasta", [
        ("Margherita Pizza", "Tomato, mozzarella and basil", 29900),
        ("Pasta Alfredo", "Creamy white sauce pasta", 26900),
        ("Pasta Arrabbiata", "Spicy tomato pasta", 24900),
        ("Bruschetta", "Tomato basil on toast", 14900),
        ("Minestrone Soup", "Vegetable soup", 13900),
        ("Tiramisu", "Coffee mascarpone dessert", 16900),
        ("Garlic Bread", "Cheesy garlic bread", 12900),
        ("Penne Pesto", "Basil pesto pasta", 27900),
        ("Lasagna", "Layered pasta bake", 31900),
        ("Caprese Salad", "Tomato, mozzarella, basil", 18900),
        ("Gelato", "Italian ice cream", 11900),
        ("Risotto", "Creamy arborio rice", 29900),
        ("Focaccia", "Olive oil flatbread", 10900),
    ]),
    ("Japanese", "Sushi", [
        ("Chicken Ramen", "Rich broth and noodles", 27900),
        ("Veg Maki Roll", "Cucumber avocado roll", 18500),
        ("Chicken Gyoza", "Pan-fried dumplings", 16900),
        ("Teriyaki Chicken Bowl", "Glazed chicken over rice", 25900),
        ("Miso Soup", "Tofu and seaweed broth", 7500),
        ("Prawn Tempura", "Crispy battered prawns", 29900),
        ("Matcha Ice Cream", "Uji matcha gelato", 11900),
        ("Salmon Nigiri", "Fresh salmon rice", 32900),
        ("Veg Tempura", "Assorted fritters", 17900),
        ("Chicken Katsu Curry", "Breaded chicken curry", 28900),
        ("Edamame", "Salted soybeans", 8900),
        ("Yakisoba", "Stir-fried noodles", 23900),
        ("Udon Soup", "Thick noodles in broth", 22900),
    ]),
    ("Mexican", "Fiesta", [
        ("Chicken Taco", "Soft taco with salsa", 15900),
        ("Veg Burrito", "Bean and rice burrito", 18900),
        ("Nachos", "Cheese and jalapenos", 14900),
        ("Quesadilla", "Cheese-filled tortilla", 17900),
        ("Guacamole", "Fresh avocado dip", 9900),
        ("Churros", "Cinnamon sugar churros", 10900),
        ("Enchilada", "Rolled tortillas in sauce", 20900),
        ("Fajita Bowl", "Grilled peppers and rice", 22900),
        ("Taco Salad", "Crisp taco salad", 16900),
        ("Salsa Trio", "Three house salsas", 7900),
        ("Mexican Rice", "Tomato rice", 11900),
        ("Flan", "Caramel custard", 9900),
        ("Elote", "Grilled corn", 8900),
    ]),
    ("Thai", "Orchid", [
        ("Green Curry", "Coconut green curry", 23900),
        ("Pad Thai", "Rice noodles with peanuts", 21900),
        ("Tom Yum Soup", "Hot and sour soup", 13900),
        ("Basil Chicken", "Spicy basil stir fry", 22900),
        ("Mango Sticky Rice", "Sweet coconut rice", 12900),
        ("Red Curry", "Coconut red curry", 23900),
        ("Som Tam", "Papaya salad", 11900),
        ("Satay Skewers", "Peanut sauce skewers", 18900),
        ("Massaman Curry", "Rich peanut curry", 24900),
        ("Thai Fried Rice", "Jasmine fried rice", 16900),
        ("Spring Rolls", "Crispy Thai rolls", 11900),
        ("Coconut Soup", "Tom kha", 12900),
        ("Pandan Cake", "Green pandan cake", 9900),
    ]),
    ("Punjabi", "Dhaba", [
        ("Dal Makhani", "Creamy black lentils", 18900),
        ("Chole Bhature", "Spiced chickpeas with bread", 16900),
        ("Butter Chicken", "Butter tomato chicken", 30900),
        ("Paneer Tikka", "Grilled paneer", 23900),
        ("Amritsari Kulcha", "Stuffed flatbread", 12900),
        ("Lassi", "Sweet yogurt drink", 6900),
        ("Rajma Chawal", "Kidney beans with rice", 15900),
        ("Sarson Ka Saag", "Mustard greens", 17900),
        ("Makki Roti", "Cornmeal flatbread", 7900),
        ("Tandoori Roti", "Whole wheat tandoor bread", 5900),
        ("Gulab Jamun", "Milk dumplings", 9900),
        ("Kadhi Pakora", "Yogurt curry with fritters", 14900),
        ("Chicken Tikka", "Grilled chicken pieces", 26900),
    ]),
    ("Street Food", "Chaat", [
        ("Pani Puri", "Crisp hollow puris with water", 6900),
        ("Bhel Puri", "Puffed rice snack", 7900),
        ("Sev Puri", "Crisp puris with chutneys", 8900),
        ("Aloo Tikki", "Spiced potato patties", 9900),
        ("Vada Pav", "Mumbai potato burger", 5900),
        ("Pav Bhaji", "Spiced vegetable mash", 11900),
        ("Dabeli", "Spiced potato bun", 6900),
        ("Samosa", "Crispy potato pastry", 4900),
        ("Kachori", "Spiced lentil pastry", 5900),
        ("Chole Kulche", "Chickpeas with bread", 10900),
        ("Frankie Roll", "Wrapped spiced filling", 9900),
        ("Cold Coffee", "Chilled coffee", 7900),
        ("Jalebi", "Crisp syrupy spirals", 6900),
    ]),
    ("Healthy", "Bowl", [
        ("Quinoa Salad", "Quinoa with vegetables", 18900),
        ("Grilled Chicken Bowl", "Chicken with brown rice", 24900),
        ("Avocado Toast", "Avocado on sourdough", 16900),
        ("Smoothie Bowl", "Fruit and granola", 14900),
        ("Roasted Veg Wrap", "Grilled vegetables in wrap", 15900),
        ("Chia Pudding", "Chia with berries", 12900),
        ("Sprout Salad", "Mixed sprouts", 10900),
        ("Oats Bowl", "Oats with nuts", 11900),
        ("Greek Yogurt Parfait", "Yogurt and fruit", 13900),
        ("Lentil Soup", "Protein lentil soup", 12900),
        ("Grilled Fish", "Herb grilled fish", 28900),
        ("Detox Juice", "Green juice", 8900),
        ("Fruit Bowl", "Seasonal fruits", 11900),
    ]),
    ("Desserts", "Sweet", [
        ("Chocolate Brownie", "Warm chocolate brownie", 12900),
        ("Cheesecake", "Creamy cheesecake", 16900),
        ("Rasmalai", "Soft chhena in milk", 11900),
        ("Kulfi", "Dense frozen dessert", 8900),
        ("Apple Pie", "Baked apple pie", 13900),
        ("Panna Cotta", "Vanilla cream", 14900),
        ("Gulab Jamun", "Syrupy dumplings", 9900),
        ("Ice Cream Sundae", "Ice cream with toppings", 12900),
        ("Carrot Cake", "Spiced carrot cake", 13900),
        ("Mousse", "Chocolate mousse", 14900),
        ("Kheer", "Rice pudding", 9900),
        ("Jalebi Rabri", "Jalebi with rabri", 12900),
        ("Brownie Sundae", "Brownie with ice cream", 14900),
    ]),
]

ADJECTIVES = ["Royal", "Urban", "Spice", "Golden", "Little", "Grand", "Coastal", "Modern", "Classic", "Fresh"]
SUFFIXES = ["Kitchen", "House", "Cafe", "Bistro", "Express", "Corner", "Studio", "Table", "Point", "Hub"]


def _restaurant_name(cuisine: str, index: int) -> str:
    adj = ADJECTIVES[index % len(ADJECTIVES)]
    suffix = SUFFIXES[(index * 3) % len(SUFFIXES)]
    return f"{adj} {cuisine} {suffix}"


RESTAURANTS = []
for i in range(36):
    cuisine, short, dishes = _CUISINES[i % len(_CUISINES)]
    rng = random.Random(1000 + i)
    menu = []
    for name, desc, price in dishes:
        if rng.random() < 0.15:
            continue
        menu.append((name, desc, price + rng.randrange(-200, 201, 50)))
    extras = {
        "North Indian": [("Paneer Lababdar", "Cottage cheese in creamy gravy", 26900), ("Veg Korma", "Mixed vegetables in cashew gravy", 21900), ("Chicken Seekh Kebab", "Minced chicken skewers", 24900)],
        "South Indian": [("Ragi Dosa", "Finger millet dosa", 13900), ("Sambar Vada", "Vada in sambar", 9900), ("Upma", "Semolina breakfast", 7900)],
        "Bengali": [("Chingri Malai Curry", "Prawn coconut curry", 33900), ("Shukto", "Bitter mixed vegetable", 14900), ("Mishti Pulao", "Sweet Bengali pulao", 17900)],
        "Chinese": [("Veg Spring Roll", "Crispy vegetable roll", 11900), ("Chicken Lollipop", "Spicy fried chicken", 19900), ("Burnt Garlic Rice", "Garlic fried rice", 16900)],
        "Italian": [("Spaghetti Bolognese", "Meat sauce pasta", 28900), ("Ravioli", "Stuffed pasta", 27900), ("Cannoli", "Crisp pastry with cream", 12900)],
        "Japanese": [("Tempura Udon", "Noodle soup with tempura", 24900), ("Chicken Teriyaki", "Glazed chicken", 26900), ("Mochi", "Soft rice cake dessert", 9900)],
        "Mexican": [("Bean Taco", "Bean filled taco", 13900), ("Chicken Enchilada", "Chicken in sauce", 21900), ("Churro Sundae", "Churros with ice cream", 12900)],
        "Thai": [("Thai Green Papaya", "Spicy papaya salad", 11900), ("Chicken Satay", "Grilled chicken skewers", 18900), ("Thai Tea", "Sweet iced tea", 7900)],
        "Punjabi": [("Amritsari Fish", "Spiced fried fish", 27900), ("Paneer Lababdar", "Rich paneer curry", 24900), ("Punjabi Kadhi", "Yogurt curry", 13900)],
        "Street Food": [("Dahi Puri", "Yogurt filled puris", 7900), ("Ragda Pattice", "Potato patties with peas", 9900), ("Kulfi Falooda", "Frozen dessert drink", 8900)],
        "Healthy": [("Protein Salad", "High protein salad", 19900), ("Grilled Tofu Bowl", "Tofu with grains", 18900), ("Green Smoothie", "Spinach fruit smoothie", 9900)],
        "Desserts": [("Chocolate Mousse", "Airy chocolate mousse", 13900), ("Fruit Tart", "Fresh fruit tart", 14900), ("Kulfi", "Dense frozen dessert", 8900)],
    }
    if len(menu) < 16:
        menu.extend([(n, d, p) for n, d, p in extras.get(cuisine, [])][:16 - len(menu)])
    if len(menu) < 10:
        menu = [(n, d, p) for n, d, p in dishes[:10]]
    RESTAURANTS.append({
        "key": f"expanded_{i:02d}",
        "name": _restaurant_name(cuisine, i),
        "description": f"{cuisine} specialties and popular dishes.",
        "cuisine": cuisine,
        "rating": 430 + (i * 7 % 55),
        "menu": menu,
    })

UNAVAILABLE_ITEMS = set()
