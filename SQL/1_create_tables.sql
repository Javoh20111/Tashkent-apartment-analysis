/* 
    'listing_id', 'price_usd', 'price_per_sqr', 'listing_type',
    'commission', 'negotiable', 'published_date', 'date_scraped', 'url',
    'description', 'housing_type', 'rooms', 'total_area_m2', 'floor',
    'total_floors', 'building_type', 'layout', 'build_year', 'age',
    'ceiling_height', 'bathroom', 'furnished', 'renovation', 'seller_type',
    'region', 'district', 'amenity_air_conditioning', 'amenity_balcony',
    'amenity_cable_tv', 'amenity_internet', 'amenity_kitchen',
    'amenity_refrigerator', 'amenity_tv', 'amenity_telephone',
    'amenity_washing_machine', 'nearby_bus_stop', 'nearby_cafe',
    'nearby_clinic', 'nearby_entertainment', 'nearby_green_area',
    'nearby_hospital', 'nearby_kindergarten', 'nearby_park',
    'nearby_parking', 'nearby_playground', 'nearby_restaurant',
    'nearby_school', 'nearby_shops', 'nearby_supermarket',
    'near_metro_mentioned'
 */

CREATE TABLE listing_fact(
    listing_id TEXT PRIMARY KEY,
    property_dim_id TEXT,
    location_dim_id TEXT,
    seller_dim_id TEXT,
    price_usd INTEGER NOT NULL,
    price_per_sqr FLOAT,
    listing_type TEXT,
    negotiable BOOLEAN,
    commission BOOLEAN,
    data_scraped DATE,
    published_date DATE,
    url TEXT,
    description TEXT
)