import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';
import { Theme, Button, Badge, Card, Flex, Text, Heading, TextField, Tabs, Switch, Callout, Spinner, Tooltip } from '@radix-ui/themes';
import '@radix-ui/themes/styles.css';
import '@fontsource/press-start-2p/latin-400.css';
import './style.css';
import './asset-detail.css';
import './gallery.css';
import { ImagePreview } from './ImagePreview';
import { Select } from './Select';

type Kind = 'sprite' | 'animation' | 'tileset' | 'image';
type Asset = { id: string; group: string; name: string; kind: Kind; origin: string; path: string; state: string; is_latest: boolean; modified_at: number; revision_hash?: string; parent_revision_hash?: string; format?: string; bytes?: number; imports: Import[]; sprite_groups?: string[]; collection_type?: string; tileset_evidence?: string; sprite_evidence?: string; resource_references?: string[] };
type Import = { name: string; state: string; scene?: string; paths: Record<string, string>; modified_files?: string[]; revision_hash?: string };
type Catalog = { project: { name: string; directory: string }; generated_at: string; assets: Asset[]; imports: Import[]; truncated: boolean; unavailable: number; scope: string };
type Clip = { name: string; fps: number; loop: boolean; duration_ms: number; frames: { frame: string; duration: number }[]; media_key?: string; contact_key?: string; source_resource?: string };
type Polygon = { points: number[][]; one_way?: boolean; one_way_margin?: number };
type Tile = { id: string; terrain: number; corners: number[]; solid: boolean; collisions?: Polygon[] };
type Detail = { name: string; kind: Kind; width: number; height: number; palette: string[]; revision_hash: string; state: string; note?: string; bytes?: number; format?: string; animated?: boolean; provenance?: Record<string, unknown>; files?: { name: string; sha256: string }[]; feedback?: { notes: { reviewer: string; reviewed_at: string; feedback: string }[] }; animations?: Clip[]; frames?: { id: string; index: number }[]; pivot?: number[]; default_animation?: string; atlas_columns?: number; tiles?: Tile[]; cells?: { x: number; y: number; tile: string }[]; terrains?: string[]; seams?: { mismatch_count: number }; collisions?: Record<string, unknown>; has_collision_preview?: boolean; collision_layer?: number; collision_mask?: number };
type Media = { data: string; mime: string; width: number; height: number; revision_hash: string };

const names: Record<Kind, string> = { sprite: 'Sprite', animation: 'Animated sprite', tileset: 'Tileset', image: 'Project image' };
const isTileset = (asset: Asset) => asset.kind === 'tileset' || asset.collection_type === 'tileset';
const isSprite = (asset: Asset) => asset.kind === 'sprite' || asset.kind === 'animation' || asset.collection_type === 'sprite';
const assetLabel = (asset: Asset) => asset.collection_type === 'tileset' ? 'Project tileset atlas' : asset.collection_type === 'sprite' ? 'Project sprite' : names[asset.kind];
const states: Record<string, string> = { draft: 'Draft', unreviewed: 'Draft', changes_requested: 'Needs changes', approved: 'Approved', imported: 'Imported', modified: 'Modified outside Daydream', project_file: 'Project file' };
const colors = { draft: 'gray', unreviewed: 'gray', changes_requested: 'amber', approved: 'green', imported: 'blue', modified: 'red', project_file: 'gray' } as const;
const token = new URLSearchParams(location.hash.slice(1)).get('token') ?? '';
const time = (value: number | string) => new Date(typeof value === 'number' ? value / 1e6 : value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
const bytes = (value?: number) => value === undefined ? '—' : value < 1024 ? `${value} B` : value < 1048576 ? `${(value / 1024).toFixed(1)} KB` : `${(value / 1048576).toFixed(1)} MB`;

// A small bounded client queue prevents thumbnail grids from overwhelming native reads.
const queue: (() => void)[] = []; let active = 0;
function schedule<T>(task: () => Promise<T>): Promise<T> {
  return new Promise((resolve, reject) => { queue.push(() => { active++; task().then(resolve, reject).finally(() => { active--; pump(); }); }); pump(); });
}
function pump() { while (active < 4 && queue.length) queue.shift()!(); }
async function api<T>(route: string, signal?: AbortSignal): Promise<T> {
  return schedule(async () => {
    if (signal?.aborted) throw new DOMException('Cancelled', 'AbortError');
    let response: Response;
    try { response = await fetch(route, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store', signal }); }
    catch (error) { if (signal?.aborted) throw error; throw new Error('Daydream is disconnected. Keep its project session open, or reopen this dashboard through /assets.'); }
    const result = await response.json();
    if (!response.ok) throw new Error(result.error ?? 'Could not read the project');
    return result;
  });
}
function useResource<T>(route: string | null, refresh: number) {
  const [state, setState] = useState<{ data?: T; error?: string; loading: boolean }>({ loading: !!route });
  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: !!route });
    if (route) api<T>(route, controller.signal).then(data => { if (!controller.signal.aborted) setState({ data, loading: false }); }, error => { if (!controller.signal.aborted) setState({ error: error.message, loading: false }); });
    return () => controller.abort();
  }, [route, refresh]);
  return state;
}
function useMedia(asset: Asset | undefined, role: string, refresh: number) {
  return useResource<Media>(asset ? `/api/media?id=${encodeURIComponent(asset.id)}&image=${encodeURIComponent(role)}` : null, refresh);
}
function useDetail(asset: Asset | undefined, refresh: number) { return useResource<Detail>(asset ? `/api/inspect?id=${encodeURIComponent(asset.id)}` : null, refresh); }
function imageURL(media: Media) { return `data:${media.mime};base64,${media.data}`; }

function StateBadge({ state }: { state: string }) { return <Badge color={colors[state as keyof typeof colors] ?? 'gray'} variant="soft">{states[state] ?? state}</Badge>; }
function Notice({ children }: { children: React.ReactNode }) { return <Callout.Root color="amber" size="1"><Callout.Text>{children}</Callout.Text></Callout.Root>; }
function Loading({ label = 'Inspecting artwork…' }: { label?: string }) { return <div className="loading"><Spinner size="3"/><div><Text color="gray" size="2">{label}</Text><Text as="p" size="1" color="gray">Check Daydream if a read-permission prompt is waiting.</Text></div></div>; }

function Thumbnail({ asset, refresh }: { asset: Asset; refresh: number }) {
  const { data, error, loading } = useMedia(asset, 'thumbnail', refresh);
  return <div className={`thumbnail ${asset.kind === 'tileset' ? 'terrain-thumb' : ''}`}>
    {data ? <img src={imageURL(data)} alt={asset.name} loading="lazy"/> : loading ? <Spinner/> : <div className="no-preview"><span>{error ? 'Preview unavailable' : assetLabel(asset)}</span></div>}
  </div>;
}

function PixelStage({ asset, role, refresh, loop = true, clip, replay = 0 }: { asset: Asset; role: string; refresh: number; zoom?: number; loop?: boolean; clip?: Clip; replay?: number; matched?: boolean }) {
  const { data, error, loading } = useMedia(asset, role, refresh);
  if (error) return <Notice>{error}</Notice>;
  if (loading || !data) return <Loading/>;
  return <ImagePreview media={data} label={`${asset.name} ${role}`} loop={loop} clip={clip} replay={replay}/>;
}

function Region({ media, index, columns, width, height, size = 64 }: { media?: Media; index: number; columns: number; width: number; height: number; size?: number }) {
  if (!media) return <Spinner/>;
  const scale = size / Math.max(width, height);
  return <div className="region" style={{ width: width * scale, height: height * scale, backgroundImage: `url(${imageURL(media)})`, backgroundSize: `${media.width * scale}px ${media.height * scale}px`, backgroundPosition: `${-(index % columns) * width * scale}px ${-Math.floor(index / columns) * height * scale}px` }}/>;
}

function Tiles({ asset, detail, refresh }: { asset: Asset; detail: Detail; refresh: number }) {
  const atlas = useMedia(asset, 'atlas', refresh);
  const [terrain, setTerrain] = useState('all'), [collision, setCollision] = useState('all'), [selected, setSelected] = useState(0), [query, setQuery] = useState('');
  const tiles = detail.tiles ?? [], tile = tiles[selected];
  const solid = (item: Tile) => item.solid || !!item.collisions?.length;
  const filtered = tiles.map((tile, index) => ({ tile, index })).filter(({ tile }) => (terrain === 'all' || String(tile.terrain) === terrain) && (collision === 'all' || (collision === 'oneway' ? tile.collisions?.some(p => p.one_way) : collision === 'solid' ? solid(tile) : !solid(tile))) && tile.id.toLowerCase().includes(query.toLowerCase()));
  return <div className="tab-body">
    <Flex gap="2" wrap="wrap"><TextField.Root placeholder="Find a tile…" value={query} onChange={e => setQuery(e.target.value)} aria-label="Find a tile"/>
      <Select.Root value={terrain} onValueChange={setTerrain}><Select.Trigger placeholder="Terrain"/><Select.Content><Select.Item value="all">All terrains</Select.Item>{detail.terrains?.map((name, index) => <Select.Item value={String(index)} key={index}>{name}</Select.Item>)}</Select.Content></Select.Root>
      <Select.Root value={collision} onValueChange={setCollision}><Select.Trigger/><Select.Content><Select.Item value="all">All collisions</Select.Item><Select.Item value="solid">Blocking</Select.Item><Select.Item value="oneway">One-way</Select.Item><Select.Item value="none">Non-blocking</Select.Item></Select.Content></Select.Root>
    </Flex>
    <Text size="2" color="gray">{filtered.length} of {tiles.length} tiles · click a tile to inspect it</Text>
    {atlas.error && <Notice>{atlas.error}</Notice>}
    {tile && <Card className="tile-inspector"><Flex gap="4" align="center"><div className="tile-large"><Region media={atlas.data} index={selected} columns={detail.atlas_columns!} width={detail.width} height={detail.height} size={112}/>
      <svg className="collision-overlay" viewBox={`0 0 ${detail.width} ${detail.height}`} aria-label="Collision geometry">{tile.collisions?.length ? tile.collisions.map((p, index) => <polygon key={index} points={p.points.map(point => point.join(',')).join(' ')} fill={p.one_way ? '#00e5ff35' : '#ffcc0035'} stroke={p.one_way ? '#00e5ff' : '#ffcc00'} strokeWidth=".35"/>) : tile.solid ? <rect x=".2" y=".2" width={detail.width - .4} height={detail.height - .4} fill="#ffcc0035" stroke="#ffcc00" strokeWidth=".35"/> : null}</svg></div>
      <div><Text weight="bold" as="div">{tile.id}</Text><Text size="2" color="gray">Tile #{selected} · {detail.width} × {detail.height} px</Text><Flex gap="2" mt="2" wrap="wrap"><Badge>{detail.terrains?.[tile.terrain] ?? 'No terrain'}</Badge><Badge color={solid(tile) ? 'amber' : 'gray'}>{solid(tile) ? 'Blocking' : 'Non-blocking'}</Badge></Flex></div></Flex>
      <Text size="2" as="p">Corners TL / TR / BR / BL: {tile.corners.map(value => value < 0 ? 'Empty' : detail.terrains?.[value] ?? value).join(' / ')}</Text>
      {!!tile.collisions?.length && <details><summary>Exact collision polygons</summary><pre>{JSON.stringify(tile.collisions, null, 2)}</pre></details>}
    </Card>}
    <div className="tile-grid">{filtered.map(({ tile, index }) => <button className={`tile ${selected === index ? 'chosen' : ''}`} key={tile.id} onClick={() => setSelected(index)} aria-label={`Inspect tile ${tile.id}`}><Region media={atlas.data} index={index} columns={detail.atlas_columns!} width={detail.width} height={detail.height}/><span>#{index}{solid(tile) && <i title="Blocking geometry"/>}</span></button>)}</div>
    {!filtered.length && <Text color="gray">No tiles match these filters.</Text>}
  </div>;
}

function ContactSheet({ asset, clip, refresh }: { asset: Asset; clip: Clip; refresh: number }) {
  const [open, setOpen] = useState(false);
  return <details className="contact-sheet" onToggle={event => setOpen(event.currentTarget.open)}><summary>Contact sheet</summary>{open && <PixelStage asset={asset} role={clip.contact_key ?? `contact:${clip.name}`} refresh={refresh} zoom={0}/>}</details>;
}

function Frames({ asset, detail, refresh, compact = false }: { asset: Asset; detail: Detail; refresh: number; compact?: boolean }) {
  const atlas = useMedia(asset, 'atlas', refresh), [selected, setSelected] = useState(0);
  return <div className="tab-body"><Text color="gray" size="2">{detail.frames?.length} source frames{detail.pivot && ` · pivot ${detail.pivot.join(', ')}`}</Text>{atlas.error && <Notice>{atlas.error}</Notice>}
    <div className="frame-large"><Region media={atlas.data} index={selected} columns={detail.atlas_columns!} width={detail.width} height={detail.height} size={compact ? 128 : 192}/><Text size="2">{detail.frames?.[selected]?.id}</Text></div>
    <div className="tile-grid">{detail.frames?.map(frame => <button key={frame.id} className={`tile ${selected === frame.index ? 'chosen' : ''}`} onClick={() => setSelected(frame.index)}><Region media={atlas.data} index={frame.index} columns={detail.atlas_columns!} width={detail.width} height={detail.height}/><span>{frame.id}</span></button>)}</div>
    {detail.animations?.map(clip => <Card key={clip.media_key ?? clip.name}><Heading size="3">{clip.name} timeline</Heading><Text color="gray" size="2">{clip.fps} FPS · {(clip.duration_ms / 1000).toFixed(2)}s · {clip.loop ? 'Looping' : 'One-shot'}</Text><ol className="timeline">{clip.frames.map((frame, index) => <li key={index}><span>{frame.frame}</span><code>{(frame.duration / clip.fps).toFixed(3)}s</code></li>)}</ol><ContactSheet asset={asset} clip={clip} refresh={refresh}/></Card>)}
  </div>;
}

function Feedback({ detail }: { detail: Detail & { approval?: { reviewer: string; reviewed_at: string }; stale_approval?: boolean } }) {
  return <div className="feedback"><Heading size="3" mb="2">Review notes</Heading>{detail.approval && <Text size="2" color="gray">Approval recorded by {detail.approval.reviewer} · {time(detail.approval.reviewed_at)}</Text>}{detail.stale_approval && <Notice>An earlier approval no longer matches this exact revision.</Notice>}{detail.feedback?.notes?.length ? detail.feedback.notes.map((note, index) => <Card key={index}><Text as="p" size="2" className="pre-wrap">{note.feedback}</Text><Text color="gray" size="1">{note.reviewer} · {time(note.reviewed_at)}</Text></Card>) : <Text size="2" color="gray">No change requests saved for this version.</Text>}</div>;
}

function AssetFacts({ detail, kind }: { detail: Detail; kind: Kind }) {
  return <div className="facts"><div><strong>{detail.width} × {detail.height}</strong><span>{kind === 'tileset' ? 'tile pixels' : 'canvas pixels'}</span></div><div><strong>{kind === 'image' ? detail.format ?? 'Image' : detail.animations?.length ?? detail.tiles?.length ?? detail.palette.length}</strong><span>{kind === 'animation' ? 'animation clips' : kind === 'tileset' ? 'tiles' : kind === 'image' ? 'source format' : 'palette colors'}</span></div></div>;
}

function SpriteAnimations({ sprite, catalog, refresh }: { sprite: Asset; catalog: Catalog; refresh: number }) {
  const associated = catalog.assets.filter(item => item.kind === 'animation' && item.sprite_groups?.includes(sprite.group));
  const [history, setHistory] = useState(false);
  const visible = associated.filter(item => history || item.is_latest);
  return <section id="sprite-animations" className="sprite-animations"><Flex align="center" justify="between" wrap="wrap" gap="3"><Heading size="4">Animations</Heading><Text as="label" size="2"><Flex align="center" gap="2"><Switch size="1" checked={history} onCheckedChange={setHistory}/>Include older versions</Flex></Text></Flex>
    <Text size="2" color="gray">{associated.length ? 'All linked clips, together. Previews repeat for review only; saved gameplay settings stay unchanged.' : 'No animations are linked to this sprite yet.'}</Text>
    <div className="animation-gallery">{visible.map(asset => <AnimationGroup key={asset.id} asset={asset} project={catalog.project.directory} refresh={refresh}/>)}</div>
  </section>;
}

function AnimationGroup({ asset, project, refresh }: { asset: Asset; project: string; refresh: number }) {
  const { data, error, loading } = useDetail(asset, refresh);
  if (loading) return <Card className="animation-card"><Text weight="bold">{asset.name}</Text><Loading label="Loading clips…"/></Card>;
  if (error) return <Card className="animation-card"><Text weight="bold">{asset.name}</Text><Notice>{error}</Notice></Card>;
  return <>{data?.animations?.map(clip => <AnimationCard key={clip.name} asset={asset} detail={data} clip={clip} project={project} refresh={refresh}/>)}</>;
}

function AnimationCard({ asset, detail, clip, project, refresh }: { asset: Asset; detail: Detail; clip: Clip; project: string; refresh: number }) {
  const [replay, setReplay] = useState(0), [open, setOpen] = useState(false), [copied, setCopied] = useState(false), [copyError, setCopyError] = useState(false);
  const command = '/assets ' + project.replace(/\/$/, '') + '/' + asset.path;
  return <Card className="animation-card" data-clip={clip.name} data-source={asset.id}><Flex align="center" justify="between" gap="2"><Heading size="3">{clip.name}</Heading><Badge color={asset.is_latest ? 'violet' : 'gray'}>{asset.is_latest ? 'Latest' : 'Older'}</Badge></Flex>
    <PixelStage asset={asset} role={clip.media_key ?? `motion:${clip.name}`} clip={clip} loop replay={replay} refresh={refresh} zoom={0}/>
    <Flex gap="2" wrap="wrap"><Badge color="gray">{clip.frames.length} frames</Badge><Badge color="gray">{clip.fps} FPS</Badge><Badge color="gray">{(clip.duration_ms / 1000).toFixed(2)}s</Badge><Badge color="gray">Saved: {clip.loop ? 'loop' : 'one-shot'}</Badge></Flex>
    <Text color="gray" size="1" className="clip-source">{asset.name}</Text><Flex gap="2" align="center" justify="between"><StateBadge state={detail.state}/><Button size="1" variant="soft" onClick={() => setReplay(value => value + 1)}>Replay</Button></Flex>
    <details onToggle={event => setOpen(event.currentTarget.open)}><summary>{clip.media_key ? 'Frames & timing' : 'Frames, feedback & review'}</summary>{open && <><Frames asset={asset} detail={detail} refresh={refresh} compact/>{clip.media_key ? <Text size="1" color="gray">Source: {clip.source_resource}. Viewing does not adopt or modify this project sprite.</Text> : <><Feedback detail={detail}/><Text as="p" color="gray" size="1">Review applies to this source animation set, not the static sprite.</Text><Button size="1" variant="soft" onClick={async () => { try { await navigator.clipboard.writeText(command); setCopied(true); } catch { setCopyError(true); } }}>{copied ? 'Copied' : 'Copy animation review command'}</Button>{copyError && <code>{command}</code>}</>}</>}</details>
  </Card>;
}

function Inspector({ asset, catalog, refresh, select, close }: { asset: Asset; catalog: Catalog; refresh: number; select: (id: string) => void; close: () => void }) {
  const { data: detail, error, loading } = useDetail(asset, refresh);
  const [tab, setTab] = useState('overview'), [loop, setLoop] = useState(true), [replay, setReplay] = useState(0), [clipName, setClipName] = useState(''), [view, setView] = useState('layout'), [compare, setCompare] = useState(false), [referenceID, setReferenceID] = useState(''), [copied, setCopied] = useState(false);
  const zoom = 0;
  const [copyError, setCopyError] = useState(false);
  const changeCompare = (enabled: boolean) => {
    if (document.startViewTransition && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      document.startViewTransition(() => flushSync(() => setCompare(enabled)));
    } else setCompare(enabled);
  };
  const family = catalog.assets.filter(item => item.group === asset.group), latest = family.find(item => item.is_latest);
  const older = family.filter(item => item.id !== asset.id && item.modified_at <= asset.modified_at);
  const reference = older.find(item => item.id === referenceID) ?? older.find(item => item.revision_hash === asset.parent_revision_hash) ?? older[0];
  const referenceDetail = useDetail(compare ? reference : undefined, refresh);
  const animationCount = catalog.assets.filter(item => item.kind === 'animation' && item.is_latest && item.sprite_groups?.includes(asset.group)).length;
  useEffect(() => { setTab('overview'); setClipName(''); setCompare(false); setReferenceID(''); setCopied(false); }, [asset.id]);
  const clip = detail?.animations?.find(item => item.name === clipName) ?? detail?.animations?.find(item => item.name === detail.default_animation) ?? detail?.animations?.[0];
  const role = asset.kind === 'sprite' ? 'sprite' : asset.kind === 'image' ? 'image' : asset.kind === 'animation' ? `motion:${clip?.name}` : view;
  const oldClip = referenceDetail.data?.animations?.find(item => item.name === clip?.name);
  const absolutePath = catalog.project.directory.replace(/\/$/, '') + '/' + asset.path;
  const reviewCommand = asset.origin === 'daydream' ? '/assets ' + absolutePath : absolutePath;
  const copy = async () => { try { await navigator.clipboard.writeText(reviewCommand); setCopied(true); setCopyError(false); } catch { setCopied(false); setCopyError(true); } };
  const information = detail && <aside className="detail-properties" aria-label="Asset information">
    <Flex gap="2" align="center" justify="between" wrap="wrap"><Heading size="3">Asset information</Heading><StateBadge state={detail.state}/></Flex><AssetFacts detail={detail} kind={asset.kind}/>
    {detail.note && <Text size="2" color="gray">{detail.note}</Text>}
    {asset.collection_type === 'sprite' && <Card><Heading size="3">Existing project sprite</Heading><Text as="p" size="2" color="gray">{detail.frames?.length ? 'Previews use the frame regions and animation timing recorded in Godot. Original files stay unchanged.' : 'No supported frame definitions were found. This is the original image; frame sizes are not guessed.'} This is not a new Daydream revision.</Text>{asset.resource_references?.map(path => <code key={path}>{path}<br/></code>)}</Card>}
    {asset.collection_type === 'tileset' && <Card><Heading size="3">Existing tileset atlas</Heading><Text as="p" size="2" color="gray">{asset.tileset_evidence === 'godot_reference' ? 'Referenced as a TileSet atlas by Godot text resources.' : 'Found in a project tileset folder.'} This is the complete atlas image. Tile sizes, terrain rules and collision shapes are not guessed from pixels; inspect those in Godot.</Text>{asset.resource_references?.map(path => <code key={path}>{path}<br/></code>)}</Card>}
    {asset.kind === 'tileset' && <><Flex gap="2" wrap="wrap"><Badge color={detail.seams?.mismatch_count ? 'amber' : 'green'}>{detail.seams?.mismatch_count ?? 0} seam mismatches</Badge><Badge color="gray">{detail.cells?.length ?? 0} placed cells</Badge><Badge color="gray">{detail.terrains?.length} terrains</Badge></Flex><details><summary>Terrain & collision details</summary><Text as="p" size="2">Collision layer: {detail.collision_layer} · mask: {detail.collision_mask}</Text><pre>{JSON.stringify({ terrains: detail.terrains, seams: detail.seams, collisions: detail.collisions }, null, 2)}</pre></details></>}
    {!!detail.palette.length && <div><Heading size="3" mb="2">Palette</Heading><div className="palette">{detail.palette.map((color, index) => <Tooltip key={color + index} content={color}><button style={{ background: color }} aria-label={`Copy color ${color}`} onClick={() => navigator.clipboard.writeText(color).catch(() => {})}/></Tooltip>)}</div></div>}
    <Feedback detail={detail}/>
    {!!asset.imports.length && <Card><Heading size="3">In your project</Heading>{asset.imports.map(record => <div key={record.name}><Text as="p" size="2">{record.name} · {states[record.state]}</Text><Text as="p" size="1" color="gray">{record.revision_hash === detail.revision_hash ? 'Registered from this revision' : 'A different revision is registered'}</Text><code>{record.scene}</code>{!!record.modified_files?.length && <Text as="p" size="2" color="amber">Manual edits are protected.</Text>}</div>)}<Text color="gray" size="1">Registered files do not prove placement in gameplay.</Text></Card>}
    <Button variant="soft" onClick={copy}>{copied ? 'Copied' : asset.origin === 'daydream' ? 'Copy review command' : 'Copy project path'}</Button><Text size="1" color="gray">{asset.origin === 'daydream' ? 'Continue review and approval in your Daydream session.' : 'Viewing does not adopt or modify this project file.'}</Text>{copyError && <code>{reviewCommand}</code>}
  </aside>;
  return <aside className="inspector" aria-label="Asset inspector">
    <div className="detail-navigation"><Button variant="soft" color="gray" onClick={close} aria-label="Back to collection">Back to collection</Button><Text size="1" color="gray">Esc to return</Text><Badge color="violet">{assetLabel(asset)}</Badge></div>
    <div className="inspector-header"><Heading size="7" className="asset-heading">{asset.name}</Heading><Flex gap="2" mt="2"><StateBadge state={detail?.state ?? asset.state}/><Badge color={asset.is_latest ? 'violet' : 'gray'}>{asset.is_latest ? 'Latest' : 'Older version'}</Badge></Flex>
    <Text color="gray" size="1" as="p">{asset.modified_at ? `Saved ${time(asset.modified_at)}` : 'Registered project resource'}</Text>
    {!asset.is_latest && latest && <Button size="1" variant="soft" onClick={() => select(latest.id)}>Open latest candidate</Button>}{asset.kind === 'sprite' && animationCount > 0 && <Button mt="3" variant="soft" onClick={() => { setTab('overview'); requestAnimationFrame(() => document.getElementById('sprite-animations')?.scrollIntoView({ block: 'start' })); }}>View animations</Button>}</div>
    {loading ? <Loading/> : error ? <div className="tab-body"><Notice>{error}</Notice><Text size="2" color="gray">The file is still listed in your collection. Refresh or inspect it in its source editor.</Text><code>{asset.path}</code></div> : detail && <>
      <Tabs.Root value={tab} onValueChange={setTab} className="inspector-tabs"><Tabs.List>
        <Tabs.Trigger value="overview">Overview</Tabs.Trigger>{asset.kind === 'tileset' && <Tabs.Trigger value="tiles">Tiles <span className="tab-count">{detail.tiles?.length}</span></Tabs.Trigger>}{asset.kind === 'animation' && <Tabs.Trigger value="frames">Frames</Tabs.Trigger>}
         {asset.kind !== 'animation' && !!detail.frames?.length && <Tabs.Trigger value="frames">Frames</Tabs.Trigger>}<Tabs.Trigger value="history">History <span className="tab-count">{family.length}</span></Tabs.Trigger><Tabs.Trigger value="files">Details</Tabs.Trigger>
      </Tabs.List>
      <Tabs.Content value="overview"><div className={`tab-body asset-detail-layout ${compare ? 'comparing' : ''}`}><div className="detail-artwork">
        {asset.kind === 'animation' && <><Select.Root value={clip?.name ?? ''} onValueChange={setClipName}><Select.Trigger aria-label="Animation clip"/><Select.Content>{detail.animations?.map(item => <Select.Item key={item.name} value={item.name}>{item.name}</Select.Item>)}</Select.Content></Select.Root><Flex gap="2" wrap="wrap"><Badge color="gray">{clip?.fps} FPS</Badge><Badge color="gray">{((clip?.duration_ms ?? 0) / 1000).toFixed(2)}s</Badge><Badge color="gray">Saved: {clip?.loop ? 'loops' : 'plays once'}</Badge></Flex></>}
        {asset.kind === 'tileset' && <Select.Root value={view} onValueChange={setView}><Select.Trigger aria-label="Tileset view"/><Select.Content><Select.Item value="layout">Placed layout</Select.Item><Select.Item value="atlas">Complete atlas</Select.Item>{detail.has_collision_preview && <Select.Item value="collisions">Collision coverage</Select.Item>}</Select.Content></Select.Root>}
        <Flex gap="3" align="center" wrap="wrap">
        {asset.kind === 'animation' && <><Text as="label" size="2"><Flex gap="2" align="center"><Switch checked={loop} onCheckedChange={setLoop} size="1"/>Loop preview</Flex></Text><Button size="1" variant="soft" onClick={() => setReplay(value => value + 1)}>Replay</Button></>}
        {!!older.length && <Text as="label" size="2"><Flex gap="2" align="center"><Switch size="1" checked={compare} onCheckedChange={changeCompare}/>Compare</Flex></Text>}</Flex>
        {!!older.length && <div className="comparison-selector-row">{compare && reference && <Select.Root value={reference.id} onValueChange={setReferenceID}><Select.Trigger aria-label="Compare version"/><Select.Content>{older.map(item => <Select.Item key={item.id} value={item.id}>{time(item.modified_at)} · {states[item.state]}</Select.Item>)}</Select.Content></Select.Root>}</div>}
        <div className="compare-stages stable-comparison"><div className="comparison-pane selected-asset-pane"><Text size="1" color="violet">Selected candidate</Text><PixelStage asset={asset} role={role} refresh={refresh} zoom={zoom} matched={compare} loop={loop} clip={clip} replay={replay}/>{information}</div>{compare && reference && <div className="comparison-pane reference-asset-pane"><Text size="1" color="gray">Earlier reference</Text>{referenceDetail.error ? <Notice>{referenceDetail.error}</Notice> : referenceDetail.loading ? <Loading/> : asset.kind === 'animation' && !oldClip ? <Notice>This version has no matching clip.</Notice> : <PixelStage asset={reference} role={role} refresh={refresh} zoom={zoom} matched loop={loop} clip={oldClip} replay={replay}/>} {referenceDetail.data && <section className="comparison-reference-info" aria-label="Reference information"><Flex gap="2" align="center" justify="between" wrap="wrap"><Heading size="3">Reference information</Heading><StateBadge state={referenceDetail.data.state}/></Flex><AssetFacts detail={referenceDetail.data} kind={reference.kind}/><Text color="gray" size="1">Saved {time(reference.modified_at)}</Text>{!!referenceDetail.data.palette.length && <div><Heading size="3">Palette</Heading><div className="palette">{referenceDetail.data.palette.map((color, index) => <span key={color + index} style={{ background: color }} title={color}/>)}</div></div>}<Feedback detail={referenceDetail.data}/></section>}</div>}</div>
        {asset.kind === 'animation' && <Text size="1" color="gray">Loop preview repeats one-shot clips for inspection only. Saved animation and gameplay settings stay unchanged.</Text>}
        {asset.kind === 'animation' && <div className="animation-gallery">{detail.animations?.map(item => <AnimationCard key={item.name} asset={asset} detail={detail} clip={item} project={catalog.project.directory} refresh={refresh}/>)}</div>}
         </div>{asset.kind === 'sprite' && <SpriteAnimations sprite={asset} catalog={catalog} refresh={refresh}/>} {asset.collection_type === 'sprite' && !!detail.animations?.length && <section id="sprite-animations" className="sprite-animations"><Heading size="4">Animations</Heading><Text size="2" color="gray">All recorded clips, together. Previews repeat for review only; saved gameplay settings stay unchanged.</Text><div className="animation-gallery">{detail.animations.map(item => <AnimationCard key={item.media_key} asset={asset} detail={detail} clip={item} project={catalog.project.directory} refresh={refresh}/>)}</div></section>}</div></Tabs.Content>
      {asset.kind === 'tileset' && <Tabs.Content value="tiles"><Tiles asset={asset} detail={detail} refresh={refresh}/></Tabs.Content>}
       {(asset.kind === 'animation' || !!detail.frames?.length) && <Tabs.Content value="frames"><Frames asset={asset} detail={detail} refresh={refresh}/></Tabs.Content>}
      <Tabs.Content value="history"><div className="tab-body"><Text size="2" color="gray">Newest saved first. Selecting history never changes approval or files.</Text>{family.map(item => <button key={item.id} className={`history-row ${item.id === asset.id ? 'chosen' : ''}`} onClick={() => select(item.id)}><div><strong>{item.is_latest ? 'Latest candidate' : 'Earlier version'}</strong><span>{time(item.modified_at)}</span></div><StateBadge state={item.state}/></button>)}</div></Tabs.Content>
      <Tabs.Content value="files"><div className="tab-body"><Heading size="3">Source & identity</Heading><Text size="2" color="gray">Project-relative source</Text><code>{asset.path}</code><Text size="2" color="gray">Validated content hash</Text><code>{detail.revision_hash}</code>{detail.bytes !== undefined && <Text size="2">Source size: {bytes(detail.bytes)}</Text>}{detail.provenance && <details><summary>Provenance</summary><pre>{JSON.stringify(detail.provenance, null, 2)}</pre></details>}{detail.files && <details><summary>Revision artifacts ({detail.files.length})</summary>{detail.files.map(file => <div className="file" key={file.name}><Text size="2" weight="bold">{file.name}</Text><code>{file.sha256}</code></div>)}</details>}{asset.imports.map(record => <details key={record.name}><summary>Managed outputs · {record.name}</summary><pre>{JSON.stringify(record.paths, null, 2)}</pre></details>)}</div></Tabs.Content>
    </Tabs.Root>
    {tab !== 'overview' && <div className="inspector-footer"><Text size="1" color="gray">{asset.origin === 'daydream' ? 'Next: review this exact candidate in Daydream.' : 'Existing project image · viewing does not adopt or modify it.'}</Text><Button variant="soft" onClick={copy}>{copied ? 'Copied' : asset.origin === 'daydream' ? 'Copy review command' : 'Copy project path'}</Button>{copied && <Text size="1" color="gray">{asset.origin === 'daydream' ? 'Paste into Daydream to continue the guided review.' : 'Paste into chat when discussing this image.'}</Text>}{copyError && <><Text size="1" color="amber">Clipboard unavailable. Select and copy this text:</Text><code>{reviewCommand}</code></>}</div>}
    </>}
  </aside>;
}

function App() {
  const initial = useMemo(() => { try { return JSON.parse(sessionStorage.getItem('daydream.dashboard') ?? '{}'); } catch { return {}; } }, []);
  const [catalog, setCatalog] = useState<Catalog>(), [busy, setBusy] = useState(true), [error, setError] = useState(''), [refresh, setRefresh] = useState(0);
  const [kind, setKind] = useState<string>(initial.kind === 'animation' ? 'sprite' : initial.kind ?? 'all'), [query, setQuery] = useState<string>(initial.query ?? ''), [state, setState] = useState<string>(initial.state ?? 'all'), [history, setHistory] = useState<boolean>(initial.history ?? false), [selectedID, setSelectedID] = useState<string>(initial.selectedID ?? ''), [page, setPage] = useState<number>(initial.page ?? 0);
  const libraryRef = useRef<HTMLElement>(null), lastCard = useRef(''), scroll = useRef(0);
  const controller = useRef<AbortController | null>(null), generation = useRef(0);
  async function reload() {
    controller.current?.abort(); const abort = new AbortController(); controller.current = abort; const current = ++generation.current;
    setBusy(true); setError('');
    try { const result = await api<Catalog>('/api/catalog', abort.signal); if (current === generation.current) { setCatalog(result); setRefresh(value => value + 1); } }
    catch (error) { if (!abort.signal.aborted) setError((error as Error).message); }
    finally { if (current === generation.current) setBusy(false); }
  }
  useEffect(() => { reload(); return () => controller.current?.abort(); }, []);
  useEffect(() => { try { sessionStorage.setItem('daydream.dashboard', JSON.stringify({ kind, query, state, history, selectedID, page })); } catch {} }, [kind, query, state, history, selectedID, page]);
  useEffect(() => setPage(0), [kind, query, state, history]);
  const all = catalog?.assets ?? [];
  const associated = (asset: Asset) => all.filter(item => item.kind === 'animation' && item.is_latest && item.sprite_groups?.includes(asset.group));
  const collection = all.filter(asset => asset.kind !== 'animation' || !asset.sprite_groups?.some(group => all.some(item => item.kind === 'sprite' && item.group === group)));
  const current = collection.filter(asset => asset.is_latest), selected = all.find(asset => asset.id === selectedID);
  const matchesKind = (asset: Asset, value: string) => value === 'all' || (value === 'sprite' ? isSprite(asset) : value === 'tileset' ? isTileset(asset) : asset.kind === 'image' && !isTileset(asset) && !isSprite(asset));
  const filtered = collection.filter(asset => (history || asset.is_latest) && matchesKind(asset, kind) && (state === 'all' || asset.state === state || associated(asset).some(item => item.state === state)) && `${asset.name} ${asset.path} ${assetLabel(asset)} ${associated(asset).map(item => item.name).join(' ')}`.toLowerCase().includes(query.toLowerCase()));
  const pages = Math.max(1, Math.ceil(filtered.length / 16)), currentPage = Math.min(page, pages - 1);
  const visible = filtered.slice(currentPage * 16, currentPage * 16 + 16);
  const select = (id: string) => { if (!selectedID) { scroll.current = libraryRef.current?.scrollTop ?? 0; lastCard.current = id; } setSelectedID(id); };
  const close = () => { setSelectedID(''); requestAnimationFrame(() => { if (libraryRef.current) { libraryRef.current.scrollTop = scroll.current; libraryRef.current.querySelector<HTMLButtonElement>(`[data-asset-id="${lastCard.current}"]`)?.focus({ preventScroll: true }); } }); };
  useEffect(() => { const key = (event: KeyboardEvent) => { if (event.key === 'Escape' && selectedID && !event.defaultPrevented) { const target = event.target as HTMLElement; if (!target.closest('[role=dialog],[role=listbox],[role=combobox]')) close(); } }; window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key); }, [selectedID]);
  return <Theme appearance="dark" accentColor="violet" grayColor="slate" radius="large" scaling="100%"><div className={`app ${selected ? 'details-open' : ''}`}>
    <aside className="sidebar"><a className="brand" href="#" aria-label="Daydream collection" onClick={event => { event.preventDefault(); close(); }}><strong><span>Day</span><span>Dream</span></strong></a>
      <div className="sidebar-label">COLLECTION</div><nav aria-label="Asset types">{(['all', 'sprite', 'tileset', 'image'] as const).map(value => <button key={value} aria-label={value === 'all' ? 'All artwork' : value === 'sprite' ? 'Sprites' : value === 'tileset' ? 'Tilesets' : 'Project images'} className={`nav-item ${kind === value ? 'active' : ''}`} onClick={() => { setKind(value); close(); }}><span>{value === 'all' ? 'All artwork' : value === 'sprite' ? 'Sprites' : value === 'tileset' ? 'Tilesets' : 'Project images'}</span><small>{current.filter(asset => matchesKind(asset, value)).length}</small></button>)}</nav>
      <div className="sidebar-bottom"><p className="workflow-note">Create · Review · Approve<br/>Add to project · Playtest</p><a href="/licenses.txt" target="_blank" rel="noreferrer">Third-party notices</a></div>
    </aside>
    <main className="main"><header className="topbar"><Heading size="6">{catalog?.project.name ?? 'Your project collection'}</Heading><div className="refresh-area"><Text size="1" color="gray">{catalog ? `Updated ${new Date(catalog.generated_at).toLocaleTimeString()}` : 'Connecting to Daydream'}</Text><Button onClick={reload} disabled={busy}>{busy ? 'Refreshing…' : 'Refresh collection'}</Button></div></header>
      {error && <div className="banner"><Notice>{error}{catalog && ' Showing the last successful snapshot; it may be stale.'}</Notice></div>}
      {catalog?.truncated && <div className="banner"><Notice>Discovery reached its bounded scan limit. This view is partial; narrow the project’s asset folders before treating it as a complete inventory.</Notice></div>}
      {!!catalog?.unavailable && <div className="banner"><Notice>{catalog.unavailable} unavailable or invalid candidate(s) could not be listed. Existing files were preserved.</Notice></div>}
      {selectedID && catalog && !selected && <div className="banner"><Notice>The selected asset is no longer in the refreshed collection. Choose another asset.</Notice></div>}
      <div className={`workspace ${selected ? 'inspecting' : ''}`}><section ref={libraryRef} className="library" aria-label="Project collection" hidden={!!selected}>
        <div className="summary-cards"><div><span>Latest artwork</span><strong>{current.length}<small>assets</small></strong></div><div><span>Needs your review</span><strong>{current.filter(asset => ['draft', 'unreviewed', 'changes_requested'].includes(asset.state)).length}<small>candidates</small></strong></div><div><span>In your project</span><strong>{catalog?.imports.length ?? 0}<small>managed imports</small></strong></div></div>
        <div className="collection-heading"><Heading size="4">{kind === 'all' ? 'Your collection' : kind === 'image' ? 'Project images' : kind === 'tileset' ? 'Tileset collection' : 'Sprite collection'}</Heading><Text color="gray" size="2">{filtered.length} {history ? 'versions & files' : 'latest assets'} · newest saved first</Text></div>
        <div className="filters"><TextField.Root placeholder="Search your artwork…" value={query} onChange={e => setQuery(e.target.value)} aria-label="Search artwork"/><Select.Root value={state} onValueChange={setState}><Select.Trigger aria-label="Review status"/><Select.Content><Select.Item value="all">All statuses</Select.Item>{Object.entries(states).filter(([key]) => key !== 'unreviewed').map(([key, label]) => <Select.Item key={key} value={key}>{label}</Select.Item>)}</Select.Content></Select.Root><Text as="label" size="2"><Flex gap="2" align="center"><Switch size="1" checked={history} onCheckedChange={setHistory}/>History</Flex></Text></div>
        {busy && !catalog ? <Loading label="Gathering your project artwork…"/> : !filtered.length ? <div className="empty"><Heading size="4">{kind === 'tileset' ? 'No tilesets found in this project' : current.length ? 'No matching artwork' : 'Your collection starts here'}</Heading><Text color="gray" size="2">{kind === 'tileset' ? 'Refresh after adding a Daydream tileset or a project atlas. PNG atlases in tileset folders and direct atlas references in Godot text resources are included; unsupported resource graphs are not reconstructed.' : current.length ? 'Try another type, status or search term.' : 'Create a candidate through /assets, or add supported images to the project, then refresh this dashboard.'}</Text>{current.length > 0 && <Button variant="soft" onClick={() => { setKind('all'); setQuery(''); setState('all'); }}>Clear filters</Button>}</div> : <div className="asset-grid">{visible.map(asset => <button key={asset.id} data-asset-id={asset.id} className="asset-card" onClick={() => select(asset.id)}><Thumbnail asset={asset} refresh={refresh}/><div className="card-info"><div className="card-title"><strong>{asset.name}</strong></div><div className="card-sub"><span>{assetLabel(asset)}</span>{asset.origin === 'daydream' && <span className={asset.is_latest ? 'latest-label' : ''}>{asset.is_latest ? 'Latest' : 'Older'}</span>}</div>{asset.kind === 'sprite' && <div className="animation-count">{associated(asset).length ? `${associated(asset).length} linked animation${associated(asset).length === 1 ? '' : 's'}` : 'Static artwork'}</div>}<div className="card-status"><StateBadge state={asset.state}/><small>{asset.modified_at ? new Date(asset.modified_at / 1e6).toLocaleDateString() : ''}</small></div></div></button>)}</div>}
        {!!filtered.length && <div className="pagination"><Text size="1" color="gray">{currentPage * 16 + 1}–{Math.min((currentPage + 1) * 16, filtered.length)} of {filtered.length}</Text><Flex gap="2"><Button size="1" color="gray" variant="soft" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>Previous</Button><Button size="1" color="gray" variant="soft" disabled={currentPage + 1 >= pages} onClick={() => setPage(currentPage + 1)}>Next</Button></Flex></div>}
        <div className="collection-footer"><Text size="1" color="gray">{catalog?.scope ?? ''}</Text></div>
      </section>{selected && catalog && <Inspector key={selected.id} asset={selected} catalog={catalog} refresh={refresh} select={select} close={close}/>}</div>
      <footer className="site-footer">Crafted by <a href="https://elevatorrobot.com" target="_blank" rel="noopener noreferrer">Elevator Robot</a></footer>
    </main>
  </div></Theme>;
}

createRoot(document.getElementById('root')!).render(<App/>);
