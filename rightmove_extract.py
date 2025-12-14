import scrapy
import re
import time
from urllib.parse import urlencode

class RealEstateSpider(scrapy.Spider):
    name = "realestatespider"
    allowed_domains = ["www.rightmove.co.uk"]
    
    # Base URL for pagination
    base_url = "https://www.rightmove.co.uk/property-for-sale/find.html"
    
    # Parameters for the search
    search_params = {
        'searchLocation': 'London',
        'useLocationIdentifier': 'true',
        'locationIdentifier': 'REGION^87490',
        'buy': 'For sale',
        'radius': '0.0',
        '_includeSSTC': 'on',
        'maxDaysSinceAdded': '3',
        'sortType': '2',
        'channel': 'BUY',
        'transactionType': 'BUY',
        'displayLocationIdentifier': 'London-87490.html',
        'includeSSTC': 'true',
        'propertyTypes': 'flat,terraced,detached,semi-detached'
    }

    def __init__(self, *args, **kwargs):
        super(RealEstateSpider, self).__init__(*args, **kwargs)
        self.max_properties = 2500  # Your target
        self.properties_scraped = 0

    custom_settings = {
        'FEEDS': {
            'real_estate_properties.jsonl': {
                'format': 'jsonlines',
                'encoding': 'utf-8',
            }
        },
        
        # Anti-bot protection
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'CONCURRENT_REQUESTS': 1,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 3,
        'RETRY_TIMES': 2,
        
        # Handle Brotli compression
        'COMPRESSION_ENABLED': True,
        
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
    }

    def start_requests(self):
        """Start with first page and handle pagination"""
        # Start from index 0 (first page)
        params = self.search_params.copy()
        params['index'] = '0'
        
        first_page_url = f"{self.base_url}?{urlencode(params)}"
        
        self.logger.info(f"🚀 Starting crawl from: {first_page_url}")
        
        yield scrapy.Request(
            url=first_page_url,
            callback=self.parse_front,
            meta={'page_number': 1}  # Start from page 1 for better logging
        )

    def parse_front(self, response):
        """Extract property links and handle pagination"""
        
        # Get current page number
        current_page = response.meta.get('page_number', 1)
        self.logger.info(f"📄 Processing page {current_page}")
        
        # Extract property links - FIXED: Get proper URLs without #/ channel parameter
        property_links = response.css('a[aria-label="Link to property details page"]::attr(href)').getall()
        
        # Clean the URLs - remove the #/ channel part
        clean_property_urls = []
        for link in property_links:
            if '#/' in link:
                # Extract just the property ID part
                property_id = link.split('/properties/')[-1].split('#')[0]
                clean_url = f"https://www.rightmove.co.uk/properties/{property_id}"
            else:
                clean_url = response.urljoin(link)
            clean_property_urls.append(clean_url)
        
        self.logger.info(f"🎯 Found {len(clean_property_urls)} properties on page {current_page}")
        
        # Follow each property link
        for property_url in clean_property_urls:
            # Stop if we reached the limit
            if self.properties_scraped >= self.max_properties:
                self.logger.info(f"✅ Reached target of {self.max_properties} properties")
                return
            
            # Add small delay between property requests
            time.sleep(1)
            
            yield scrapy.Request(
                url=property_url,
                callback=self.parse_page,
                meta={'page_number': current_page}
            )
        
        # PAGINATION: Check if we should go to next page
        if self.properties_scraped < self.max_properties:
            # FIXED: Better pagination detection
            next_page_url = self._get_next_page_url(response, current_page)
            
            if next_page_url:
                next_page_number = current_page + 1
                
                self.logger.info(f"➡️ Moving to page {next_page_number}")
                
                # Add delay before next page
                time.sleep(3)
                
                yield scrapy.Request(
                    url=next_page_url,
                    callback=self.parse_front,
                    meta={'page_number': next_page_number}
                )
            else:
                self.logger.info("❌ No more pages available")
        else:
            self.logger.info(f"✅ Reached target of {self.max_properties} properties")

    def _get_next_page_url(self, response, current_page):
        """Extract next page URL using multiple strategies"""
        
        # Strategy 1: Look for next button by text
        next_button = response.xpath('//button[contains(@class, "pagination") and contains(text(), "Next")]')
        if next_button and not next_button.attrib.get('disabled'):
            # Get the next page index
            next_index = current_page * 24
            params = self.search_params.copy()
            params['index'] = str(next_index)
            return f"{self.base_url}?{urlencode(params)}"
        
        # Strategy 2: Look for pagination next arrow
        next_arrow = response.css('button[data-test="pagination-next"]')
        if next_arrow and not next_arrow.attrib.get('disabled'):
            next_index = current_page * 24
            params = self.search_params.copy()
            params['index'] = str(next_index)
            return f"{self.base_url}?{urlencode(params)}"
        
        # Strategy 3: Look for pagination links with numbers
        pagination_links = response.css('div.pagination a::attr(href)').getall()
        if pagination_links:
            # Find the next page link (current page + 1)
            for link in pagination_links:
                if f'index={current_page * 24}' in link:
                    return response.urljoin(link)
        
        # Strategy 4: Manually construct next page URL
        next_index = current_page * 24
        # Check if next index is reasonable (Rightmove usually has up to 1000+ results)
        if next_index < 1200:  # 50 pages * 24 properties
            params = self.search_params.copy()
            params['index'] = str(next_index)
            next_url = f"{self.base_url}?{urlencode(params)}"
            
            # Log that we're trying manual pagination
            self.logger.info(f"🔧 Trying manual pagination to index {next_index}")
            return next_url
        
        return None

    def parse_page(self, response):
        """Extract property details from individual property page"""
        
        # Validate response
        if not self._is_valid_response(response):
            self.logger.warning(f"Invalid property page response: {response.url}")
            return
        
        try:
            property_data = self._parse_rightmove(response)
            
            # Only yield if we have meaningful data
            if property_data and (property_data.get('price') or property_data.get('location')):
                self.properties_scraped += 1
                self.logger.info(f"📊 Scraped {self.properties_scraped}/{self.max_properties} properties")
                yield property_data
            else:
                self.logger.warning(f"Insufficient data at {response.url}")
                
        except Exception as e:
            self.logger.error(f"Error parsing {response.url}: {str(e)}")

    def _is_valid_response(self, response):
        """Validate that response is proper HTML content"""
        if response.status != 200:
            return False
            
        if not response.body:
            return False
            
        try:
            content_type = response.headers.get('Content-Type', b'').decode('utf-8', errors='ignore').lower()
            if 'text/html' not in content_type:
                return False
        except:
            return False
            
        try:
            body_text = response.text
            if not body_text or '<html' not in body_text.lower():
                return False
        except:
            return False
            
        return True

    def _parse_rightmove(self, response):
        """Parse Rightmove property page with proper class matching"""
        try:
            # Use contains to match the class (handles extra spaces)
            property_info = response.css('p[class*="_1hV1kqpVceE9m-QrX_hWDN"]::text').getall()
            
            # Extract other data...
            video_thumbnail_style = response.css('a[title="Video Tour"] div::attr(style)').get()
            video_thumbnail_url = None
            if video_thumbnail_style:
                url_match = re.search(r"url\(['\"]?(.*?)['\"]?\)", video_thumbnail_style)
                if url_match:
                    video_thumbnail_url = url_match.group(1)
            
            description_parts = response.xpath('//div/h2[text()="Description"]/following-sibling::div[1]//text()').extract()
            description_clean = self._clean_description(description_parts)
            
            features_raw = response.xpath('//article[@data-testid="primary-layout"]//li[@class="lIhZ24u1NHMa5Y6gDH90A"]/text()').extract()
            features_clean = [feature.strip() for feature in features_raw if feature.strip()]
            
            return {
                "source": "rightmove",
                "type": property_info[0].strip() if len(property_info) > 0 and property_info[0] else None,
                "beds": property_info[1].strip() if len(property_info) > 1 and property_info[1] else None,
                "baths": property_info[2].strip() if len(property_info) > 2 and property_info[2] else None,
                "area": property_info[3].strip() if len(property_info) > 3 and property_info[3] else None,
                "price": response.css('div[class="_1gfnqJ3Vtd1z40MlC0MzXu"] span::text').get(),
                "location": response.css('h1[itemprop="streetAddress"]::text').get(),
                "features": features_clean,
                "description": description_clean,
                "photos_url": response.css('a[itemprop="photo"] meta[itemprop="contentUrl"]::attr(content)').getall(),
                "video_url": response.css('a[title="Video Tour"]::attr(href)').get(),
                "video_thumbnail": video_thumbnail_url,
                "url": response.url,
                "property_info_count": len(property_info),
                "page_number": response.meta.get('page_number', 'unknown')
            }
            
        except Exception as e:
            self.logger.error(f"Error in _parse_rightmove for {response.url}: {e}")
            return {}

    def _clean_description(self, description_parts):
        """Clean and join description parts"""
        if not description_parts:
            return None
        try:
            full_description = ' '.join(''.join(description_parts).split())
            return full_description if full_description else None
        except:
            return None