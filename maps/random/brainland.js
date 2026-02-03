/*jslint bitwise: true, browser: true, evil:true, devel: true, todo: true, debug: true, nomen: true, plusplus: true, sloppy: true, vars: true, white: true, indent: 2 */
/*globals
  uneval, log, TERRAIN_SEPARATOR, PI, TWO_PI,
  cos, sin, round, randInt, abs, floor,
  g_MapSettings,
  randomizeBiome, InitMap, getNumPlayers, createTileClass, placeTerrain, sortPlayers, getMapSize, randFloat, createArea,
  scaleByMapSize, fractionToTiles, addToClass, createObjectGroup, createStragglerTrees,
  placeGenericFortress, placeObject, placePolygonalWall,
  ClumpPlacer, LayeredPainter, SimpleGroup, SimpleObject, createFood,
  avoidClasses, createBumps, createHills, createMines, createDecoration, createForests, createMountains, createLayeredPatches, createPatches,
  rBiomeT1, rBiomeT2, rBiomeT3, rBiomeT4, rBiomeT5, rBiomeT6, rBiomeT7, rBiomeT8, rBiomeT10, rBiomeT11, rBiomeT12,
  rBiomeE1, rBiomeE2, rBiomeE3, rBiomeE4, rBiomeE5, rBiomeE6, rBiomeE7, rBiomeE8, rBiomeE10, rBiomeE11, rBiomeE12, rBiomeE13,
  rBiomeA1, rBiomeA2, rBiomeA5, rBiomeA6, rBiomeA7, rBiomeA8,
  ExportMap
*/

// rmghelper
/*globals H */

var tt = Date.now();
var g_Map; // Global map object

// Constants that were provided by old 0AD engine
var PI = Math.PI;
var TWO_PI = 2 * Math.PI;

// Math functions that were provided by old 0AD engine as globals
var cos = Math.cos;
var sin = Math.sin;
var round = Math.round;
var randInt = function(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
};
var abs = Math.abs;
var floor = Math.floor;
var randFloat = function(min, max) {
  return Math.random() * (max - min) + min;
};

Engine.LoadLibrary("rmgen");
Engine.LoadLibrary("rmgen-common");
Engine.LoadLibrary("rmghelper"); // import H.deb/fmt

// Stub functions for compatibility with modern 0AD API
// In modern 0AD, biomes are handled differently via setBiome() and g_Terrains/g_Gaia/g_Decoratives
// These stubs provide a single biome (temperate) for compatibility

// Initialize the map using modern RandomMap API
function InitMap() {
  if (typeof g_Map === 'undefined') {
    g_Map = new RandomMap(3, "temperate_grass_03");
  }
}

// Stub function for compatibility
function getMapSize() {
  return g_Map.size;
}

// Stub function for compatibility
function createTileClass() {
  return g_Map.createTileClass();
}

// Stub function for compatibility - places terrain at specific tile coordinates
function placeTerrain(x, z, texture) {
  g_Map.setTexture(new Vector2D(x, z), texture);
}

// Stub function for compatibility - adds a tile to a tile class
function addToClass(x, z, tileClass) {
  tileClass.add(new Vector2D(x, z));
}

// Stub function for compatibility - places an entity at specific position
function placeObject(x, z, template, player, angle) {
  var entity = new Entity(g_Map.getEntityID(), template, player, new Vector2D(x, z), angle);
  g_Map.entities.push(entity);
}

// Stub function for compatibility - exports the map
function ExportMap() {
  return g_Map;
}

function randomizeBiome() {
  return 1; // Return temperate biome index
}

// Terrain stubs - temperate biome values
function rBiomeT1() { return "temperate_grass_03"; }  // Main terrain
function rBiomeT2() { return "temperate_grass_01"; }  // Forest floor 1
function rBiomeT3() { return "temperate_grass_02"; }  // Forest floor 2
function rBiomeT4() { return "temperate_cliff_01"; }  // Cliff
function rBiomeT5() { return "temperate_mud_01"; }    // Tier 1 terrain
function rBiomeT6() { return "temperate_grass_dirt_01"; } // Tier 2 terrain
function rBiomeT7() { return "temperate_grass_dirt_03"; } // Tier 3 terrain
function rBiomeT8() { return "temperate_rocks_dirt_01"; }  // Hill
function rBiomeT10() { return "temperate_paving_03"; }  // Road
function rBiomeT11() { return "temperate_paving_03"; }  // Road wild
function rBiomeT12() { return "temperate_grass_mud_01"; } // Tier 4 terrain

// Entity stubs - gaia entities
function rBiomeE1() { return "gaia/tree/poplar_dead"; }  // Tree 1
function rBiomeE2() { return "gaia/tree/deciduous_02"; } // Tree 2
function rBiomeE3() { return "gaia/tree/euro_beech"; }   // Tree 3
function rBiomeE4() { return "gaia/tree/carob"; }        // Tree 4
function rBiomeE5() { return "gaia/tree/olive"; }       // Tree 5
function rBiomeE6() { return "gaia/fruit/berry_01"; }    // Fruit bush
function rBiomeE7() { return "gaia/fauna_chicken"; }     // Chicken
function rBiomeE8() { return "gaia/fauna_deer"; }        // Main huntable animal
function rBiomeE10() { return "gaia/fauna_sheep"; }       // Secondary huntable animal
function rBiomeE11() { return "gaia/rock/temperate_large_02"; } // Stone large
function rBiomeE12() { return "gaia/rock/temperate_small"; }   // Stone small
function rBiomeE13() { return "gaia/ore/temperate_01"; }       // Metal large

// Actor stubs - decorative props
function rBiomeA1() { return "actor|props/flora/grass_soft_large_tall.xml"; } // Grass
function rBiomeA2() { return "actor|props/flora/grass_soft_large.xml"; }    // Grass short
function rBiomeA5() { return "actor|geology/stone_granite_med.xml"; }      // Rock large
function rBiomeA6() { return "actor|geology/stone_granite_small.xml"; }    // Rock medium
function rBiomeA7() { return "actor|flora/trees/temperate_bush_biome.xml"; } // Bush medium
function rBiomeA8() { return "actor|props/flora/bush_medit_sm.xml"; }      // Bush small

// /Daten/Projects/Osiris/ps/trunk/binaries/data/mods/public/civs[civ].json.StartEntities

var START = {
  "athen" : [
      [1, "structures/athen/civil_centre"],
      [4, "units/athen/support_female_citizen"],
      [2, "units/athen/infantry_spearman_b"],
      [2, "units/athen/infantry_slinger_b"],
      [1, "units/athen/cavalry_javelineer_b"],
    ],
    "brit" : [
      [1, "structures/brit/civil_centre"],
      [4, "units/brit/support_female_citizen"],
      [2, "units/brit/infantry_spearman_b"],
      [2, "units/brit/infantry_slinger_b"],
      [1, "units/brit/cavalry_javelineer_b"],
      [1, "units/brit/war_dog"],
    ],
    "cart" : [
      [1, "structures/cart/civil_centre"],
      [4, "units/cart/support_female_citizen"],
      [2, "units/cart/infantry_spearman_b"],
      [2, "units/cart/infantry_archer_b"],
      [1, "units/cart/cavalry_javelineer_b"],
    ],
    "gaul" : [
      [1, "structures/gaul/civil_centre"],
      [4, "units/gaul/support_female_citizen"],
      [2, "units/gaul/infantry_spearman_b"],
      [2, "units/gaul/infantry_javelineer_b"],
      [1, "units/gaul/cavalry_javelineer_b"],
    ],
    "iber" : [
      [1, "structures/iber/civil_centre"],
      [4, "units/iber/support_female_citizen"],
      [2, "units/iber/infantry_swordsman_b"],
      [2, "units/iber/infantry_javelineer_b"],
      [1, "units/iber/cavalry_javelineer_b"],
    ],
    "mace" : [
      [1, "structures/mace/civil_centre"],
      [4, "units/mace/support_female_citizen"],
      [2, "units/mace/infantry_pikeman_b"],
      [2, "units/mace/infantry_javelineer_b"],
      [1, "units/mace/cavalry_spearman_b"],
    ],
    "maur" : [
      [1, "structures/maur/civil_centre"],
      [4, "units/maur/support_female_citizen"],
      [2, "units/maur/infantry_spearman_b"],
      [2, "units/maur/infantry_archer_b"],
      [1, "units/maur/cavalry_javelineer_b"],
      [1, "units/maur/support_elephant"],
    ],
    "pers" : [
      [1, "structures/pers/civil_centre"],
      [4, "units/pers/support_female_citizen"],
      [2, "units/pers/infantry_spearman_b"],
      [2, "units/pers/infantry_archer_b"],
      [1, "units/pers/cavalry_javelineer_b"],
    ],
    "ptol" : [
      [1, "structures/ptol/civil_centre"],
      [4, "units/ptol/support_female_citizen"],
      [2, "units/ptol/infantry_pikeman_b"],
      [2, "units/ptol/infantry_slinger_b"],
      [1, "units/ptol/cavalry_archer_b"],
    ],
    "rome" : [
      [1, "structures/rome/civil_centre"],
      [4, "units/rome/support_female_citizen"],
      [2, "units/rome/infantry_swordsman_b"],
      [2, "units/rome/infantry_javelineer_b"],
      [1, "units/rome/cavalry_spearman_b"],
    ],
    "sele" : [
      [1, "structures/sele/civil_centre"],
      [4, "units/sele/support_female_citizen"],
      [2, "units/sele/infantry_spearman_b"],
      [2, "units/sele/infantry_javelineer_b"],
      [1, "units/sele/cavalry_javelineer_b"],
    ],
    "spart" : [
      [1, "structures/spart/civil_centre"],
      [4, "units/spart/support_female_citizen"],
      [2, "units/spart/infantry_spearman_b"],
      [2, "units/spart/infantry_javelineer_b"],
      [1, "units/spart/cavalry_javelineer_b"],
    ],
  };

function getCCEntities (civ /*, bot */){
  return START[civ].map(function(c){return {Template: c[1], Count: c[0]};} );
}

// [
//  {Template:"structures/athen_civil_centre"}, 
//  {Template:"units/athen_support_female_citizen", Count:4}, 
//  {Template:"units/athen_infantry_spearman_b", Count:2}, 
//  {Template:"units/athen_infantry_slinger_b", Count:2}, 
//  {Template:"units/athen_cavalry_javelinist_b"}
// ]


//random terrain textures - will be initialized in GenerateMap()
var random_terrain, numPlayers, mapSize,
  tMainTerrain, tForestFloor1, tForestFloor2, tCliff,
  tTier1Terrain, tTier2Terrain, tTier3Terrain, tHill,
  tRoad, tRoadWild, tTier4Terrain,
  oTree1, oTree2, oTree3, oTree4, oTree5,
  oFruitBush, oChicken, oMainHuntableAnimal, oSecondaryHuntableAnimal,
  oStoneLarge, oStoneSmall, oMetalLarge,
  aGrass, aGrassShort, aRockLarge, aRockMedium, aBushMedium, aBushSmall,
  pForest1, pForest2, clPlayer, clHill, clForest, clRock, clMetal, clFood, clBaseResource;

// initialize map - moved into GenerateMap()
// log("Initializing map...");
// InitMap();
// const numPlayers = getNumPlayers();
// const mapSize = getMapSize();

// silly globals - moved into GenerateMap()
var group, playerIDs, playerX, playerZ, playerAngle;

// create tile classes - moved into GenerateMap()
// var clPlayer = createTileClass(), clHill = createTileClass(), ...



function step0  (/* options */) {
  for (var ix = 0; ix < mapSize; ix++)
  {
    for (var iz = 0; iz < mapSize; iz++)
    {
      var x = ix / (mapSize + 1.0);
      var z = iz / (mapSize + 1.0);
        placeTerrain(ix, iz, tMainTerrain);
    }
  }
}

function step1  (/* options */) {
  playerIDs = [];
  for (var i = 0; i < numPlayers; i++)
  {
    playerIDs.push(i+1);
  }
  playerIDs = sortPlayers(playerIDs);
}

function step2Old  (/* options */) {

  playerX = new Array(numPlayers);
  playerZ = new Array(numPlayers);
  playerAngle = new Array(numPlayers);

  var startAngle = randFloat(0, TWO_PI);
  for (var i = 0; i < numPlayers; i++)
  {
    playerAngle[i] = startAngle + i*TWO_PI/numPlayers;
    playerX[i] = 0.5 + 0.35*cos(playerAngle[i]);
    playerZ[i] = 0.5 + 0.35*sin(playerAngle[i]);
  }
}

function step2  (/* options */) {

  playerX = new Array(numPlayers);
  playerZ = new Array(numPlayers);
  playerAngle = new Array(numPlayers);

  var factor = {
    "0": 1.00,
    "1": 1.00,
    "2": 1.00,
    "3": 1.25,
    "4": 1.50,
    "5": 1.75,
    "6": 2.00,
    "7": 2.25,
    "8": 2.50,
  }[numPlayers];

  var startAngle = randFloat(0, TWO_PI);
  for (var i = 0; i < numPlayers; i++)
  {
    playerAngle[i] = startAngle + i*TWO_PI/numPlayers;
    playerX[i] = 0.5 + 0.14*cos(playerAngle[i]) * factor;
    playerZ[i] = 0.5 + 0.14*sin(playerAngle[i]) * factor;
  }
}

function step3  (/* options */) {

  var i, j, id, num;

  for (i = 0; i < numPlayers; i++){

    id = playerIDs[i];

    // H.deb(" i: %s %s %s", i, id, uneval(g_MapSettings));

    // some constants
    var radius = scaleByMapSize(15, 25);

    log("Creating base for player " + id + "...");
    
    // some constants
    // var radius = scaleByMapSize(15,25);
    // var cliffRadius = 2;
    // var elevation = 20;
    
    // get the x and z in tiles
    var fx = fractionToTiles(playerX[i]);
    var fz = fractionToTiles(playerZ[i]);
    var angle = playerAngle[i] + Math.PI;
    var ix = round(fx);
    var iz = round(fz);

    // Get civ from g_MapSettings - modern 0AD API
    var civ;
    if (g_MapSettings && g_MapSettings.PlayerData && g_MapSettings.PlayerData[id-1]) {
      civ = g_MapSettings.PlayerData[id-1].Civ;
    } else {
      // Fallback to default if not available
      civ = "athen";
    }

    addToClass(ix, iz, clPlayer);
    addToClass(ix+5, iz, clPlayer);
    addToClass(ix, iz+5, clPlayer);
    addToClass(ix-5, iz, clPlayer);
    addToClass(ix, iz-5, clPlayer);
    
    // create starting units
    // placeCivDefaultEntities(fx, fz, id, BUILDING_ANGlE);

    (function placeCivDefaultEntities(fx, fz, playerid, angle, kwargs) {
      
      // Unpack kwargs
      kwargs = (kwargs || {});
      var iberWall = "walls";
      if (getMapSize() <= 128)
        iberWall = false;
      if ("iberWall" in kwargs)
        iberWall = kwargs["iberWall"];
      
      // Place default civ starting entities
      // var civEntities = getStartingEntities(playerid-1);
      var civEntities = getCCEntities(civ, playerid-1);

      // distance of units from CC
      var uDist = 10;
      var uSpace = 2;

      // CC
      placeObject(fx, fz, civEntities[0].Template, playerid, angle);
      
      // all other
      for (var j = 1; j < civEntities.length; ++j){

        var uAngle = angle - PI * (2-j) / 2;
        var count = (civEntities[j].Count !== undefined ? civEntities[j].Count : 1);
        for (var numberofentities = 0; numberofentities < count; numberofentities++){

          var ux = fx + uDist * cos(uAngle) + numberofentities * uSpace * cos(uAngle + PI/2) - (0.75 * uSpace * floor(count / 2) * cos(uAngle + PI/2));
          var uz = fz + uDist * sin(uAngle) + numberofentities * uSpace * sin(uAngle + PI/2) - (0.75 * uSpace * floor(count / 2) * sin(uAngle + PI/2));
          placeObject(ux, uz, civEntities[j].Template, playerid, uAngle); 

          // H.deb("%s, %s, %s, %s, %s", ux, uz, civEntities[j].Template, playerid, uAngle)

        }
      }
      
      // Add defensive structiures for Iberians as their civ bonus
      if (civ === "iber" && iberWall !== false){
        if (iberWall === "towers"){
          placePolygonalWall(fx, fz, 15, ["entry"], "tower", civ, playerid, angle, 7);
        } else {
          placeGenericFortress(fx, fz, 20/*radius*/, playerid);}
      }

    }(fx, fz, id, angle));

    // create the city patch
    var cityRadius = radius/3;
    // Modified for modern API: ClumpPlacer(size, coherence, smoothness, failFraction, centerPosition)
    var placer = new ClumpPlacer(PI*cityRadius*cityRadius, 0.6, 0.3, 0, new Vector2D(ix, iz));
    var painter = new LayeredPainter([tRoadWild, tRoad], [1]);

    createArea(placer, painter, null);
    
    // create animals
    for (j = 0; j < 2; ++j)
    {
      var aAngle = randFloat(0, TWO_PI);
      var aDist = 7;
      var aX = round(fx + aDist * cos(aAngle));
      var aZ = round(fz + aDist * sin(aAngle));

      group = new SimpleGroup(
        [new SimpleObject(oChicken, 5,5, 0,2)],
        true, clBaseResource, new Vector2D(aX, aZ)
      );
      createObjectGroup(group, 0);
    }
    
    // create berry bushes
    var bbAngle = randFloat(0, TWO_PI);
    var bbDist = 12;
    var bbX = round(fx + bbDist * cos(bbAngle));
    var bbZ = round(fz + bbDist * sin(bbAngle));
    group = new SimpleGroup(
      [new SimpleObject(oFruitBush, 5,5, 0,3)],
      true, clBaseResource, new Vector2D(bbX, bbZ)
    );
    createObjectGroup(group, 0);    
    // create metal mine
    var mAngle = bbAngle;
    while(abs(mAngle - bbAngle) < PI/3)
    {
      mAngle = randFloat(0, TWO_PI);
    }
    var mDist = 12;
    var mX = round(fx + mDist * cos(mAngle));
    var mZ = round(fz + mDist * sin(mAngle));
    group = new SimpleGroup(
      [new SimpleObject(oMetalLarge, 1,1, 0,0)],
      true, clBaseResource, new Vector2D(mX, mZ)
    );
    createObjectGroup(group, 0);
    
    // create stone mines
    mAngle += randFloat(PI/8, PI/4);
    mX = round(fx + mDist * cos(mAngle));
    mZ = round(fz + mDist * sin(mAngle));
    group = new SimpleGroup(
      [new SimpleObject(oStoneLarge, 1,1, 0,2)],
      true, clBaseResource, new Vector2D(mX, mZ)
    );
    createObjectGroup(group, 0);
    var hillSize = PI * radius * radius;
    // create starting trees
    num = 5;
    var tAngle = randFloat(0, TWO_PI);
    var tDist = randFloat(12, 13);
    var tX = round(fx + tDist * cos(tAngle));
    var tZ = round(fz + tDist * sin(tAngle));
    group = new SimpleGroup(
      [new SimpleObject(oTree1, num, num, 0,3)],
      false, clBaseResource, new Vector2D(tX, tZ)
    );
    createObjectGroup(group, 0, avoidClasses(clBaseResource,2));
    
    // create grass tufts
    num = hillSize / 250;
    for (j = 0; j < num; j++)
    {
      var gAngle = randFloat(0, TWO_PI);
      var gDist = radius - (5 + randInt(7));
      var gX = round(fx + gDist * cos(gAngle));
      var gZ = round(fz + gDist * sin(gAngle));
      group = new SimpleGroup(
        [new SimpleObject(aGrassShort, 2,5, 0,1, -PI/8,PI/8)],
        false, clBaseResource, new Vector2D(gX, gZ)
      );
      createObjectGroup(group, 0);
    }
  }
}


function step4a  (/* options */) {

  // create bumps
  createBumps();

}

function step4b  (/* options */) {

  // create hills
  if (randInt(1, 2) == 1)
    createHills([tCliff, tCliff, tHill], avoidClasses(clPlayer, 20, clHill, 15), clHill, scaleByMapSize(3, 15));
  else
    createMountains(tCliff, avoidClasses(clPlayer, 20, clHill, 15), clHill, scaleByMapSize(3, 15));
}

function step4c  (multiplier=1.0) {

  // create forests
  createForests(
    [tMainTerrain, tForestFloor1, tForestFloor2, pForest1, pForest2],
    avoidClasses(clPlayer, 20, clForest, 18, clHill, 0), 
    clForest,
    multiplier,
    random_terrain
  );
}

function step5  (/* options */) {

  // create dirt patches
  createLayeredPatches(
    [scaleByMapSize(3, 6), scaleByMapSize(5, 10), scaleByMapSize(8, 21)],
    [[tMainTerrain,tTier1Terrain],[tTier1Terrain,tTier2Terrain], [tTier2Terrain,tTier3Terrain]],
    [1,1]
  );

  // create grass patches
  log("Creating grass patches...");
  createPatches(
    [scaleByMapSize(2, 4), scaleByMapSize(3, 7), scaleByMapSize(5, 15)],
    tTier4Terrain
  );
}

function step6  (/* options */) {

  // create stone quarries
  createMines(
   [
    [new SimpleObject(oStoneSmall, 0,2, 0,4), new SimpleObject(oStoneLarge, 1,1, 0,4)],
    [new SimpleObject(oStoneSmall, 2,5, 1,3)]
   ]
  );

  log("Creating metal mines...");
  // create large metal quarries
  createMines(
   [
    [new SimpleObject(oMetalLarge, 1,1, 0,4)]
   ],
   avoidClasses(clForest, 1, clPlayer, 20, clMetal, 10, clRock, 5, clHill, 1),
   clMetal
  );

}

function step7  (/* options */) {

  var planetm = 1;

  if (random_terrain==7)
    planetm = 8;

  createDecoration
  (
   [[new SimpleObject(aRockMedium, 1,3, 0,1)], 
    [new SimpleObject(aRockLarge, 1,2, 0,1), new SimpleObject(aRockMedium, 1,3, 0,2)],
    [new SimpleObject(aGrassShort, 1,2, 0,1, -PI/8,PI/8)],
    [new SimpleObject(aGrass, 2,4, 0,1.8, -PI/8,PI/8), new SimpleObject(aGrassShort, 3,6, 1.2,2.5, -PI/8,PI/8)],
    [new SimpleObject(aBushMedium, 1,2, 0,2), new SimpleObject(aBushSmall, 2,4, 0,2)]
   ],
   [
    scaleByMapSize(16, 262),
    scaleByMapSize(8, 131),
    planetm * scaleByMapSize(13, 200),
    planetm * scaleByMapSize(13, 200),
    planetm * scaleByMapSize(13, 200)
   ]
  );
}

function step8  (/* options */) {

  createFood
  (
   [
    [new SimpleObject(oMainHuntableAnimal, 5,7, 0,4)],
    [new SimpleObject(oSecondaryHuntableAnimal, 2,3, 0,2)]
   ], 
   [
    3 * numPlayers,
    3 * numPlayers
   ]
  );
}

function step9  (/* options */) {

  createFood
  (
   [
    [new SimpleObject(oFruitBush, 5,7, 0,4)]
   ], 
   [
    3 * numPlayers
   ],
   avoidClasses(clForest, 0, clPlayer, 20, clHill, 1, clFood, 10)
  );
}

function step10  (/* options */) {

  var types = [oTree1, oTree2, oTree4, oTree3]; // some variation
  createStragglerTrees(types);

}
// Export map data

// H.deb("global %s", typeof global);

// H.logObject(global, "brainland.global");

var sequence = [
  [ 2, step0,  "Place terrain",               {}],
  [ 3, step1,  "Randomize player order",      {}],
  [ 5, step2,  "Place players",               {}],
  [10, step3,  "Creating village",            {}],
  // [20, step4a,  "Creating bumps", {}],
  // [30, step4b,  "Creating hills/mountains", {}],
  [40, step4c,  "Creating forests", 0.5],
  // [50, step5,  "Creating dirt/grass patches", {}],
  [55, step6,  "Creating stone/metal mines",  {}],
  // [65, step7,  "Creating decoration",         {}],
  // [70, step8,  "Creating animals",            {}],
  // [75, step9,  "Creating fruits",             {}],
  [85, step10, "Creating straggler trees",    {}],
];

function tab (s,l){l=l||4;s=new Array(l+1).join(" ")+s;return s.substr(s.length-l);}

// Main generator function required by modern 0AD
function* GenerateMap()
{
  // Initialize map
  log("Initializing map...");
  InitMap();

  // Set terrain and biome variables
  random_terrain = randomizeBiome();

  tMainTerrain  = rBiomeT1();
  tForestFloor1 = rBiomeT2();
  tForestFloor2 = rBiomeT3();
  tCliff        = rBiomeT4();
  tTier1Terrain = rBiomeT5();
  tTier2Terrain = rBiomeT6();
  tTier3Terrain = rBiomeT7();
  tHill         = rBiomeT8();
  tRoad         = rBiomeT10();
  tRoadWild     = rBiomeT11();
  tTier4Terrain = rBiomeT12();

  oTree1        = rBiomeE1();
  oTree2        = rBiomeE2();
  oTree3        = rBiomeE3();
  oTree4        = rBiomeE4();
  oTree5        = rBiomeE5();
  oFruitBush    = rBiomeE6();
  oChicken      = rBiomeE7();
  oMainHuntableAnimal = rBiomeE8();
  oSecondaryHuntableAnimal = rBiomeE10();
  oStoneLarge   = rBiomeE11();
  oStoneSmall   = rBiomeE12();
  oMetalLarge   = rBiomeE13();

  aGrass        = rBiomeA1();
  aGrassShort   = rBiomeA2();
  aRockLarge    = rBiomeA5();
  aRockMedium   = rBiomeA6();
  aBushMedium   = rBiomeA7();
  aBushSmall    = rBiomeA8();

  pForest1 = [tForestFloor2 + TERRAIN_SEPARATOR + oTree1, tForestFloor2 + TERRAIN_SEPARATOR + oTree2, tForestFloor2];
  pForest2 = [tForestFloor1 + TERRAIN_SEPARATOR + oTree4, tForestFloor1 + TERRAIN_SEPARATOR + oTree5, tForestFloor1];

  // Set map dimensions
  numPlayers = getNumPlayers();
  mapSize = getMapSize();

  // Create tile classes
  clPlayer  = createTileClass();
  clHill    = createTileClass();
  clForest  = createTileClass();
  clRock    = createTileClass();
  clMetal   = createTileClass();
  clFood    = createTileClass();
  clBaseResource = createTileClass();

  // Initialize player variables
  group = [];
  playerIDs = [];
  playerX = [];
  playerZ = [];
  playerAngle = [];

  // Execute map generation steps
  H.deb("generating: brainland / %s, %s players, size: %s ### ---", H.biomes[random_terrain], numPlayers, mapSize);
  sequence.forEach(function (task){
    var t0 = Date.now();
    log(task[2]);
    task[1].apply(null, task.slice(3));
    H.deb("  %s -> %s | %s ...", tab(Date.now() - t0), task[2], JSON.stringify(task.slice(3)));
  });

  H.deb("finished: brainland (" + sequence.length + " steps in " + ((Date.now() - tt)/1000).toFixed(1) + " secs) ### ---\n");

  return g_Map;
}