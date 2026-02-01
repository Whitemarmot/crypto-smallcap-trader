/**
 * Twitter/X Scraper
 * Uses Nitter instances (public Twitter frontend) for scraping
 * Also supports official API if credentials provided
 */

import axios, { AxiosInstance } from 'axios';
import * as cheerio from 'cheerio';
import { SocialPost, ScrapedData } from '../types';

// Public Nitter instances (these change frequently)
const NITTER_INSTANCES = [
  'https://nitter.net',
  'https://nitter.privacydev.net',
  'https://nitter.poast.org',
  'https://nitter.1d4.us',
];

// Crypto Twitter accounts to monitor
export const CRYPTO_INFLUENCERS = [
  'CryptoWizardd',
  'CryptoBanter',
  'AltcoinGordon',
  'CryptoGodJohn',
  'MoonOverlord',
  'crypto_bitlord',
  'TheCryptoLark',
  'Pentosh1',
  'CryptoKaleo',
  'inversebrah',
];

export class TwitterScraper {
  private client: AxiosInstance;
  private nitterIndex: number = 0;
  private lastRequestTime: number = 0;
  private minRequestInterval: number = 3000; // 3 seconds
  private bearerToken?: string;
  
  constructor(bearerToken?: string) {
    this.bearerToken = bearerToken;
    this.client = axios.create({
      timeout: 15000,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
      },
    });
  }
  
  /**
   * Rate limit helper
   */
  private async rateLimit(): Promise<void> {
    const now = Date.now();
    const timeSinceLastRequest = now - this.lastRequestTime;
    if (timeSinceLastRequest < this.minRequestInterval) {
      await new Promise(resolve => 
        setTimeout(resolve, this.minRequestInterval - timeSinceLastRequest)
      );
    }
    this.lastRequestTime = Date.now();
  }
  
  /**
   * Get next Nitter instance (rotate on failures)
   */
  private getNitterInstance(): string {
    const instance = NITTER_INSTANCES[this.nitterIndex];
    this.nitterIndex = (this.nitterIndex + 1) % NITTER_INSTANCES.length;
    return instance;
  }
  
  /**
   * Search tweets via Nitter
   */
  async search(query: string, limit: number = 20): Promise<ScrapedData> {
    await this.rateLimit();
    
    // Try multiple Nitter instances
    for (let attempt = 0; attempt < NITTER_INSTANCES.length; attempt++) {
      const instance = this.getNitterInstance();
      
      try {
        const response = await this.client.get(`${instance}/search`, {
          params: { f: 'tweets', q: query },
        });
        
        const posts = this.parseNitterSearch(response.data, instance);
        
        return {
          posts: posts.slice(0, limit),
          scrapedAt: new Date(),
          source: `twitter:search:${query}`,
          hasMore: posts.length >= limit,
        };
      } catch (error) {
        console.warn(`Nitter instance ${instance} failed, trying next...`);
        continue;
      }
    }
    
    // All Nitter instances failed
    console.error('All Nitter instances failed');
    return {
      posts: [],
      scrapedAt: new Date(),
      source: `twitter:search:${query}`,
      hasMore: false,
    };
  }
  
  /**
   * Fetch user timeline via Nitter
   */
  async fetchUserTimeline(username: string, limit: number = 20): Promise<ScrapedData> {
    await this.rateLimit();
    
    for (let attempt = 0; attempt < NITTER_INSTANCES.length; attempt++) {
      const instance = this.getNitterInstance();
      
      try {
        const response = await this.client.get(`${instance}/${username}`);
        const posts = this.parseNitterTimeline(response.data, username, instance);
        
        return {
          posts: posts.slice(0, limit),
          scrapedAt: new Date(),
          source: `twitter:user:${username}`,
          hasMore: posts.length >= limit,
        };
      } catch (error) {
        console.warn(`Failed to fetch @${username} from ${instance}`);
        continue;
      }
    }
    
    return {
      posts: [],
      scrapedAt: new Date(),
      source: `twitter:user:${username}`,
      hasMore: false,
    };
  }
  
  /**
   * Fetch multiple influencer timelines
   */
  async fetchInfluencers(
    accounts: string[] = CRYPTO_INFLUENCERS,
    limitPerAccount: number = 5
  ): Promise<SocialPost[]> {
    const allPosts: SocialPost[] = [];
    
    for (const account of accounts) {
      const result = await this.fetchUserTimeline(account, limitPerAccount);
      allPosts.push(...result.posts);
    }
    
    return allPosts.sort((a, b) => 
      b.timestamp.getTime() - a.timestamp.getTime()
    );
  }
  
  /**
   * Search for token mentions
   */
  async searchToken(tokenSymbol: string): Promise<SocialPost[]> {
    const searchTerms = [
      `$${tokenSymbol}`,
      `#${tokenSymbol}`,
      tokenSymbol,
    ];
    
    const allPosts: SocialPost[] = [];
    
    for (const term of searchTerms) {
      const result = await this.search(term, 15);
      allPosts.push(...result.posts);
    }
    
    // Deduplicate
    const seen = new Set<string>();
    return allPosts.filter(post => {
      if (seen.has(post.id)) return false;
      seen.add(post.id);
      return true;
    });
  }
  
  /**
   * Parse Nitter search results HTML
   */
  private parseNitterSearch(html: string, baseUrl: string): SocialPost[] {
    const $ = cheerio.load(html);
    const posts: SocialPost[] = [];
    
    $('.timeline-item').each((_, element) => {
      try {
        const $el = $(element);
        
        const id = $el.find('.tweet-link').attr('href')?.split('/').pop() || '';
        const author = $el.find('.username').text().replace('@', '').trim();
        const content = $el.find('.tweet-content').text().trim();
        const timeStr = $el.find('.tweet-date a').attr('title') || '';
        
        // Parse engagement stats
        const stats = $el.find('.tweet-stats');
        const comments = this.parseStatNumber(stats.find('.icon-comment').parent().text());
        const shares = this.parseStatNumber(stats.find('.icon-retweet').parent().text());
        const likes = this.parseStatNumber(stats.find('.icon-heart').parent().text());
        
        if (id && content) {
          posts.push({
            id: `twitter_${id}`,
            platform: 'twitter',
            author,
            content,
            timestamp: timeStr ? new Date(timeStr) : new Date(),
            engagement: { likes, comments, shares },
            url: `https://twitter.com/${author}/status/${id}`,
          });
        }
      } catch (e) {
        // Skip malformed tweets
      }
    });
    
    return posts;
  }
  
  /**
   * Parse Nitter user timeline HTML
   */
  private parseNitterTimeline(html: string, username: string, baseUrl: string): SocialPost[] {
    // Same parsing logic as search
    return this.parseNitterSearch(html, baseUrl);
  }
  
  /**
   * Parse stat numbers (handles K, M suffixes)
   */
  private parseStatNumber(text: string): number {
    const cleaned = text.replace(/[^0-9.KMkm]/g, '').trim();
    if (!cleaned) return 0;
    
    const num = parseFloat(cleaned);
    if (cleaned.toLowerCase().includes('k')) return num * 1000;
    if (cleaned.toLowerCase().includes('m')) return num * 1000000;
    return Math.floor(num);
  }
  
  /**
   * Use official Twitter API v2 (if bearer token provided)
   */
  async searchOfficial(query: string, maxResults: number = 10): Promise<ScrapedData> {
    if (!this.bearerToken) {
      console.warn('No Twitter bearer token provided, falling back to Nitter');
      return this.search(query, maxResults);
    }
    
    await this.rateLimit();
    
    try {
      const response = await axios.get(
        'https://api.twitter.com/2/tweets/search/recent',
        {
          params: {
            query: `${query} -is:retweet`,
            max_results: maxResults,
            'tweet.fields': 'created_at,public_metrics,author_id',
          },
          headers: {
            'Authorization': `Bearer ${this.bearerToken}`,
          },
        }
      );
      
      const posts: SocialPost[] = (response.data.data || []).map((tweet: any) => ({
        id: `twitter_${tweet.id}`,
        platform: 'twitter' as const,
        author: tweet.author_id, // Would need user lookup for username
        content: tweet.text,
        timestamp: new Date(tweet.created_at),
        engagement: {
          likes: tweet.public_metrics?.like_count || 0,
          comments: tweet.public_metrics?.reply_count || 0,
          shares: tweet.public_metrics?.retweet_count || 0,
        },
      }));
      
      return {
        posts,
        scrapedAt: new Date(),
        source: `twitter:api:${query}`,
        hasMore: !!response.data.meta?.next_token,
        cursor: response.data.meta?.next_token,
      };
    } catch (error) {
      console.error('Twitter API error:', error);
      // Fallback to Nitter
      return this.search(query, maxResults);
    }
  }
}

export const twitterScraper = new TwitterScraper();
