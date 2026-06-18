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

CREATE TABLE property_dim (
    property_dim_id TEXT PRIMARY KEY,
    housing_type TEXT, 
    rooms INTEGER, 
    total_area_m2 FLOAT, 
    floor INTEGER,
    total_floors INTEGER, 
    building_type TEXT, 
    layout TEXT, 
    build_year INTEGER, 
    age INTEGER,
    ceiling_height DECIMAL(3,2), 
    bathroom TEXT, 
    furnished BOOLEAN, 
    renovation TEXT
)

CREATE TABLE location_dim (
    location_dim_id TEXT PRIMARY KEY,
    region TEXT,
    district TEXT
)

CREATE TABLE listing_fact(
    listing_id TEXT PRIMARY KEY,
    property_dim_id TEXT,
    location_dim_id TEXT,
    seller_dim_id TEXT,
    seller_type TEXT,
    price_usd INTEGER NOT NULL,
    price_per_sqr FLOAT,
    listing_type TEXT,
    negotiable BOOLEAN,
    commission BOOLEAN,
    date_scraped DATE,
    published_date DATE,
    url TEXT,
    description TEXT,
    FOREIGN KEY (property_dim_id) REFERENCES property_dim(property_dim_id),
    FOREIGN KEY (location_dim_id) REFERENCES location_dim(location_dim_id),
    FOREIGN KEY (seller_dim_id)   REFERENCES seller_dim(seller_dim_id)
)


CREATE TABLE listing_attributes(
    listing_id TEXT,
    amenity_air_conditioning BOOLEAN,
    amenity_balcony BOOLEAN,
    amenity_cable_tv BOOLEAN,
    amenity_internet BOOLEAN,
    amenity_kitchen BOOLEAN,
    amenity_refrigerator BOOLEAN,
    amenity_tv BOOLEAN,
    amenity_telephone BOOLEAN,
    amenity_washing_machine BOOLEAN,
    nearby_bus_stop BOOLEAN,
    nearby_cafe BOOLEAN,
    nearby_clinic BOOLEAN,
    nearby_entertainment BOOLEAN,
    nearby_green_area BOOLEAN,
    nearby_hospital BOOLEAN,
    nearby_kindergarten BOOLEAN,
    nearby_parking BOOLEAN,
    nearby_playground BOOLEAN,
    near_metro_mentioned BOOLEAN,
    nearby_restaurant BOOLEAN,
    nearby_school BOOLEAN,
    nearby_shops BOOLEAN,
    nearby_supermarket BOOLEAN,
    FOREIGN KEY (listing_id) REFERENCES listing_fact(listing_id)
)

