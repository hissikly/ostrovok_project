[out:json][timeout:300];
(
  nwr["shop"](43.37,39.62,43.67,40.03);
  nwr["amenity"~"^(pharmacy|cafe|restaurant|fast_food|bar|pub|nightclub|atm|bank|hospital|clinic|doctors|dentist|parking|charging_station|fuel|marketplace|place_of_worship|ice_cream|car_rental|bicycle_rental|post_office|kindergarten|cinema|theatre|bus_station|ferry_terminal|veterinary|toilets|drinking_water)$"](43.37,39.62,43.67,40.03);
  nwr["leisure"~"^(park|garden|playground|fitness_centre|sports_centre|dog_park|water_park|swimming_pool|fitness_station|pitch|stadium)$"](43.37,39.62,43.67,40.03);
  nwr["tourism"~"^(museum|attraction|viewpoint|zoo|aquarium|theme_park|gallery)$"](43.37,39.62,43.67,40.03);
  node["highway"="bus_stop"](43.37,39.62,43.67,40.03);
  nwr["railway"~"^(station|halt)$"](43.37,39.62,43.67,40.03);
  nwr["healthcare"](43.37,39.62,43.67,40.03);
);
out center tags qt;
