/**
 * Reddit Scraper
 * Uses Reddit's public JSON API (no auth required for public posts)
 */

import axios, { AxiosInstance } from 'axios';
import { SocialPost, ScrapedData } from '../types';

// Crypto-related subreddits for smallcap hunting
export const CRYPTO_SUBREDDITS = [
  'CryptoMoonShots',
  'altcoin',
  'SatoshiStreetBets',
  'CryptoMarkets',
  'smallcapcoins',
  'CryptoCurrency',
  'defi',
  'memecoin',
  'solana',
  'ethtrader',
];

interface RedditPost {
  data: {
    id: string;
    title: string;
    selftext: string;
    author: string;
    created_utc: number;
    score: number;
    num_comments: number;
    url: string;
    subreddit: string;
    upvote_ratio: number;
  };
}

interface RedditResponse {
  data: {
    children: RedditPost[];
    after: string | null;
  };
}

export class RedditScraper {
  private client: AxiosInstance;
  private lastRequestTime: number = 0;
  private minRequestInterval: number = 2000; // 2 seconds between requests (respect rate limits)
  
  constructor() {
    this.client = axios.create({
      baseURL: 'https://www.reddit.com',
      headers: {
        'User-Agent': 'CryptoSentimentBot/1.0 (Educational purposes)',
        'Accept': 'application/json',
      },
      timeout: 15000,
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
   * Fetch posts from a subreddit
   */
  async fetchSubreddit(
    subreddit: string,
    sort: 'hot' | 'new' | 'rising' | 'top' = 'hot',
    limit: number = 25,
    after?: string
  ): Promise<ScrapedData> {
    await this.rateLimit();
    
    try {
      const params: Record<string, string | number> = { limit };
      if (after) params.after = after;
      
      const response = await this.client.get<RedditResponse>(
        `/r/${subreddit}/${sort}.json`,
        { params }
      );
      
      const posts = response.data.data.children.map(post => 
        this.transformPost(post)
      );
      
      return {
        posts,
        scrapedAt: new Date(),
        source: `reddit:${subreddit}`,
        hasMore: !!response.data.data.after,
        cursor: response.data.data.after || undefined,
      };
    } catch (error) {
      console.error(`Error fetching r/${subreddit}:`, error);
      return {
        posts: [],
        scrapedAt: new Date(),
        source: `reddit:${subreddit}`,
        hasMore: false,
      };
    }
  }
  
  /**
   * Search Reddit for specific terms
   */
  async search(
    query: string,
    subreddit?: string,
    sort: 'relevance' | 'hot' | 'top' | 'new' = 'new',
    limit: number = 25
  ): Promise<ScrapedData> {
    await this.rateLimit();
    
    try {
      const params: Record<string, string | number> = {
        q: query,
        sort,
        limit,
        restrict_sr: subreddit ? 1 : 0,
      };
      
      const endpoint = subreddit 
        ? `/r/${subreddit}/search.json`
        : '/search.json';
      
      const response = await this.client.get<RedditResponse>(endpoint, { params });
      
      const posts = response.data.data.children.map(post => 
        this.transformPost(post)
      );
      
      return {
        posts,
        scrapedAt: new Date(),
        source: `reddit:search:${query}`,
        hasMore: !!response.data.data.after,
        cursor: response.data.data.after || undefined,
      };
    } catch (error) {
      console.error(`Error searching Reddit for "${query}":`, error);
      return {
        posts: [],
        scrapedAt: new Date(),
        source: `reddit:search:${query}`,
        hasMore: false,
      };
    }
  }
  
  /**
   * Fetch from multiple subreddits
   */
  async fetchMultipleSubreddits(
    subreddits: string[] = CRYPTO_SUBREDDITS,
    sort: 'hot' | 'new' | 'rising' | 'top' = 'hot',
    limitPerSubreddit: number = 15
  ): Promise<SocialPost[]> {
    const allPosts: SocialPost[] = [];
    
    for (const subreddit of subreddits) {
      const result = await this.fetchSubreddit(subreddit, sort, limitPerSubreddit);
      allPosts.push(...result.posts);
    }
    
    // Sort by timestamp (newest first)
    return allPosts.sort((a, b) => 
      b.timestamp.getTime() - a.timestamp.getTime()
    );
  }
  
  /**
   * Search for token mentions across crypto subreddits
   */
  async searchToken(
    tokenSymbol: string,
    subreddits: string[] = CRYPTO_SUBREDDITS
  ): Promise<SocialPost[]> {
    const allPosts: SocialPost[] = [];
    const searchTerms = [
      `$${tokenSymbol}`,
      tokenSymbol,
    ];
    
    for (const term of searchTerms) {
      for (const subreddit of subreddits.slice(0, 5)) { // Limit to avoid rate limits
        const result = await this.search(term, subreddit, 'new', 10);
        allPosts.push(...result.posts);
      }
    }
    
    // Deduplicate by ID
    const seen = new Set<string>();
    return allPosts.filter(post => {
      if (seen.has(post.id)) return false;
      seen.add(post.id);
      return true;
    });
  }
  
  /**
   * Transform Reddit API response to SocialPost
   */
  private transformPost(redditPost: RedditPost): SocialPost {
    const { data } = redditPost;
    
    return {
      id: `reddit_${data.id}`,
      platform: 'reddit',
      author: data.author,
      content: `${data.title}\n\n${data.selftext || ''}`.trim(),
      timestamp: new Date(data.created_utc * 1000),
      engagement: {
        likes: data.score,
        comments: data.num_comments,
        shares: 0, // Reddit doesn't expose this
      },
      url: `https://reddit.com${data.url}`,
      subreddit: data.subreddit,
    };
  }
}

export const redditScraper = new RedditScraper();
