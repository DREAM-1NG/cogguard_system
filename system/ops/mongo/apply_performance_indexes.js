const databaseName = process.env.MONGO_DATABASE || "cogguard";
const dryRun = ["1", "true", "yes"].includes(
  String(process.env.MONGO_PERFORMANCE_INDEXES_DRY_RUN || "").toLowerCase(),
);
const target = db.getSiblingDB(databaseName);

const definitions = [
  {
    collection: "raw_posts",
    name: "ix_raw_posts_event_platform_timestamp",
    key: { event_id: 1, platform: 1, timestamp: -1 },
    purpose: "event and platform scoped acquisition, analysis, and time ordering",
  },
  {
    collection: "raw_posts",
    name: "ix_raw_posts_event_timestamp",
    key: { event_id: 1, timestamp: -1 },
    purpose: "event-scoped dashboard and acquisition ordering",
  },
  {
    collection: "raw_posts",
    name: "ix_raw_posts_platform_timestamp",
    key: { platform: 1, timestamp: -1 },
    purpose: "platform-scoped acquisition ordering",
  },
  {
    collection: "raw_posts",
    name: "ix_raw_posts_timestamp",
    key: { timestamp: -1 },
    purpose: "unfiltered acquisition ordering",
  },
  {
    collection: "raw_posts",
    name: "ix_raw_posts_crawl_job_id",
    key: { crawl_job_id: 1 },
    purpose: "crawl-job cleanup",
  },
  {
    collection: "raw_comments",
    name: "ix_raw_comments_event_platform_timestamp",
    key: { event_id: 1, platform: 1, timestamp: -1 },
    purpose: "event and platform scoped comment loading",
  },
  {
    collection: "raw_comments",
    name: "ix_raw_comments_platform_timestamp",
    key: { platform: 1, timestamp: -1 },
    purpose: "platform-scoped comment loading",
  },
  {
    collection: "raw_comments",
    name: "ix_raw_comments_crawl_job_id",
    key: { crawl_job_id: 1 },
    purpose: "crawl-job cleanup",
  },
];

function keySignature(key) {
  return JSON.stringify(Object.entries(key));
}

const results = [];
for (const definition of definitions) {
  const collection = target.getCollection(definition.collection);
  const existing = collection
    .getIndexes()
    .find((index) => index.name === definition.name);

  if (existing) {
    if (keySignature(existing.key) !== keySignature(definition.key)) {
      throw new Error(
        `Index ${definition.collection}.${definition.name} exists with a different key: ${JSON.stringify(existing.key)}`,
      );
    }
    results.push({ ...definition, status: "already_present" });
    continue;
  }

  if (dryRun) {
    results.push({ ...definition, status: "planned" });
    continue;
  }

  collection.createIndex(definition.key, { name: definition.name });
  results.push({ ...definition, status: "created" });
}

printjson({
  database: databaseName,
  dry_run: dryRun,
  indexes: results,
});
