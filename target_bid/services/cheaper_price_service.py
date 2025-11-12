from target_bid.repository.scraped_product_repo import ScrapedProductRepository

repo = ScrapedProductRepository()

def get_cheaper_alternatives(material_name, unit, current_price):
    return repo.find_cheaper_same_unit(material_name, unit, current_price)
