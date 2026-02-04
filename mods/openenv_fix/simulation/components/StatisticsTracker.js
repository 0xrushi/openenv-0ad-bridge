function StatisticsTracker() {}

StatisticsTracker.prototype.Schema =
	"<a:help>This component records statistics over the course of the match, such as the number of trained, lost, captured and destroyed units and buildings The statistics are consumed by the summary screen and lobby rankings.</a:help>" +
	"<a:example>" +
		"<UnitClasses>Infantry FemaleCitizen</UnitClasses>" +
		"<StructureClasses>House Wonder</StructureClasses>" +
	"</a:example>" +
	"<element name='UnitClasses' a:help='The tracker records trained, lost, killed and captured units of entities that match any of these Identity classes.'>" +
		"<attribute name='datatype'>" +
			"<value>tokens</value>" +
		"</attribute>" +
		"<text/>" +
	"</element>" +
	"<element name='StructureClasses' a:help='The tracker records constructed, lost, destroyed and captured structures of entities that match any of these Identity classes.'>" +
		"<attribute name='datatype'>" +
			"<value>tokens</value>" +
		"</attribute>" +
		"<text/>" +
	"</element>";

/**
 * This number specifies the time in milliseconds between consecutive statistics snapshots recorded.
 */
StatisticsTracker.prototype.UpdateSequenceInterval = 30 * 1000;

StatisticsTracker.prototype.Init = function()
{
	this.unitsClasses = this.template.UnitClasses._string.split(/\s+/);
	this.buildingsClasses = this.template.StructureClasses._string.split(/\s+/);

	this.unitsTrained = {};
	this.unitsLost = {};
	this.enemyUnitsKilled = {};
	this.unitsCaptured = {};

	this.unitsLostValue = 0;
	this.enemyUnitsKilledValue = 0;
	this.unitsCapturedValue = 0;

	for (let counterName of ["unitsTrained", "unitsLost", "enemyUnitsKilled", "unitsCaptured"])
	{
		this[counterName].total = 0;
		for (let unitClass of this.unitsClasses)
			// Domestic units are only counted for training
			if (unitClass != "Domestic" || counterName == "unitsTrained")
				this[counterName][unitClass] = 0;
	}

	this.buildingsConstructed = {};
	this.buildingsLost = {};
	this.enemyBuildingsDestroyed = {};
	this.buildingsCaptured = {};

	this.buildingsLostValue = 0;
	this.enemyBuildingsDestroyedValue = 0;
	this.buildingsCapturedValue = 0;

	for (let counterName of ["buildingsConstructed", "buildingsLost", "enemyBuildingsDestroyed", "buildingsCaptured"])
	{
		this[counterName].total = 0;
		for (let unitClass of this.buildingsClasses)
			this[counterName][unitClass] = 0;
	}

	this.resourcesGathered = {
		"vegetarianFood": 0
	};
	this.resourcesUsed = {};
	this.resourcesSold = {};
	this.resourcesBought = {};
	for (let res of Resources.GetCodes())
	{
		this.resourcesGathered[res] = 0;
		this.resourcesUsed[res] = 0;
		this.resourcesSold[res] = 0;
		this.resourcesBought[res] = 0;
	}

	this.tributesSent = 0;
	this.tributesReceived = 0;
	this.tradeIncome = 0;
	this.treasuresCollected = 0;
	this.lootCollected = 0;
	this.peakPercentMapControlled = 0;
	this.teamPeakPercentMapControlled = 0;
	this.successfulBribes = 0;
	this.failedBribes = 0;

	let cmpTimer = Engine.QueryInterface(SYSTEM_ENTITY, IID_Timer);
	this.updateTimer = cmpTimer.SetInterval(
		this.entity, IID_StatisticsTracker, "UpdateSequences", 0, this.UpdateSequenceInterval);
};

StatisticsTracker.prototype.OnGlobalInitGame = function()
{
	this.sequences = clone(this.GetStatistics());
	this.sequences.time = [];
};

StatisticsTracker.prototype.GetBasicStatistics = function()
{
	return {
		"resourcesGathered": this.resourcesGathered,
		"percentMapExplored": this.GetPercentMapExplored()
	};
};

StatisticsTracker.prototype.GetStatistics = function()
{
	return {
		"unitsTrained": this.unitsTrained,
		"unitsLost": this.unitsLost,
		"unitsLostValue": this.unitsLostValue,
		"enemyUnitsKilled": this.enemyUnitsKilled,
		"enemyUnitsKilledValue": this.enemyUnitsKilledValue,
		"unitsCaptured": this.unitsCaptured,
		"unitsCapturedValue": this.unitsCapturedValue,
		"buildingsConstructed": this.buildingsConstructed,
		"buildingsLost": this.buildingsLost,
		"buildingsLostValue": this.buildingsLostValue,
		"enemyBuildingsDestroyed": this.enemyBuildingsDestroyed,
		"enemyBuildingsDestroyedValue": this.enemyBuildingsDestroyedValue,
		"buildingsCaptured": this.buildingsCaptured,
		"buildingsCapturedValue": this.buildingsCapturedValue,
		"resourcesCount": this.GetResourceCounts(),
		"resourcesGathered": this.resourcesGathered,
		"resourcesUsed": this.resourcesUsed,
		"resourcesSold": this.resourcesSold,
		"resourcesBought": this.resourcesBought,
		"tributesSent": this.tributesSent,
		"tributesReceived": this.tributesReceived,
		"tradeIncome": this.tradeIncome,
		"treasuresCollected": this.treasuresCollected,
		"lootCollected": this.lootCollected,
		"populationCount": this.GetPopulationCount(),
		"percentMapExplored": this.GetPercentMapExplored(),
		"teamPercentMapExplored": this.GetTeamPercentMapExplored(),
		"percentMapControlled": this.GetPercentMapControlled(),
		"teamPercentMapControlled": this.GetTeamPercentMapControlled(),
		"peakPercentMapControlled": this.peakPercentMapControlled,
		"teamPeakPercentMapControlled": this.teamPeakPercentMapControlled,
		"successfulBribes": this.successfulBribes,
		"failedBribes": this.failedBribes
	};
};

StatisticsTracker.prototype.GetSequences = function()
{
	if (!this.sequences)
		this.OnGlobalInitGame();

	let ret = clone(this.sequences);
	let cmpTimer = Engine.QueryInterface(SYSTEM_ENTITY, IID_Timer);

	ret.time.push(cmpTimer.GetTime() / 1000);
	this.PushValue(this.GetStatistics(), ret);
	return ret;
};

StatisticsTracker.prototype.GetStatisticsJSON = function()
{
	let cmpPlayer = Engine.QueryInterface(this.entity, IID_Player);

	let playerStatistics = {
		"playerID": cmpPlayer.GetPlayerID(),
		"playerState": cmpPlayer.GetState(),
		"statistics": this.GetStatistics()
	};

	return JSON.stringify(playerStatistics, null, "\t");
};

StatisticsTracker.prototype.CounterIncrement = function(classes, counter, type)
{
	if (!classes)
		return;

	if (classes.includes(type))
		++this[counter][type];
};

StatisticsTracker.prototype.IncreaseTrainedUnitsCounter = function(trainedUnit)
{
	const classes = Engine.QueryInterface(trainedUnit, IID_Identity)?.GetClassesList();
	if (!classes)
		return;

	for (const type of this.unitsClasses)
		this.CounterIncrement(classes, "unitsTrained", type);

	if (!classes.includes("Domestic"))
		++this.unitsTrained.total;
};

StatisticsTracker.prototype.IncreaseConstructedBuildingsCounter = function(constructedBuilding)
{
	const classes = Engine.QueryInterface(constructedBuilding, IID_Identity)?.GetClassesList();
	if (!classes)
		return;

	for (const type of this.buildingsClasses)
		this.CounterIncrement(classes, "buildingsConstructed", type);

	++this.buildingsConstructed.total;
};

StatisticsTracker.prototype.KilledEntity = function(targetEntity)
{
	const cmpTargetEntityIdentity = Engine.QueryInterface(targetEntity, IID_Identity);
	if (!cmpTargetEntityIdentity)
		return;

	const classes = cmpTargetEntityIdentity.GetClassesList();
	const costs = Engine.QueryInterface(targetEntity, IID_Cost)?.GetResourceCosts();

	if (cmpTargetEntityIdentity.HasClass("Unit") && !cmpTargetEntityIdentity.HasClass("Animal"))
	{
		for (const type of this.unitsClasses)
			this.CounterIncrement(classes, "enemyUnitsKilled", type);

		if (costs)
			for (const type in costs)
				this.enemyUnitsKilledValue += costs[type];
	}

	if (cmpTargetEntityIdentity.HasClass("Structure") && !Engine.QueryInterface(targetEntity, IID_Foundation))
	{
		for (const type of this.buildingsClasses)
			this.CounterIncrement(classes, "enemyBuildingsDestroyed", type);

		if (costs)
			for (const type in costs)
				this.enemyBuildingsDestroyedValue += costs[type];
	}
};

StatisticsTracker.prototype.LostEntity = function(lostEntity)
{
	const cmpLostEntityIdentity = Engine.QueryInterface(lostEntity, IID_Identity);
	if (!cmpLostEntityIdentity)
		return;

	const classes = cmpLostEntityIdentity.GetClassesList();
	const costs = Engine.QueryInterface(lostEntity, IID_Cost)?.GetResourceCosts();

	if (cmpLostEntityIdentity.HasClass("Unit") && !cmpLostEntityIdentity.HasClass("Domestic"))
	{
		for (const type of this.unitsClasses)
			this.CounterIncrement(classes, "unitsLost", type);

		if (costs)
			for (const type in costs)
				this.unitsLostValue += costs[type];
	}

	if (cmpLostEntityIdentity.HasClass("Structure") && !Engine.QueryInterface(lostEntity, IID_Foundation))
	{
		for (const type of this.buildingsClasses)
			this.CounterIncrement(classes, "buildingsLost", type);

		if (costs)
			for (const type in costs)
				this.buildingsLostValue += costs[type];
	}
};

StatisticsTracker.prototype.CapturedEntity = function(capturedEntity)
{
	const cmpCapturedEntityIdentity = Engine.QueryInterface(capturedEntity, IID_Identity);
	if (!cmpCapturedEntityIdentity)
		return;

	const classes = cmpCapturedEntityIdentity.GetClassesList();
	const costs = Engine.QueryInterface(capturedEntity, IID_Cost)?.GetResourceCosts();

	if (cmpCapturedEntityIdentity.HasClass("Unit"))
	{
		for (const type of this.unitsClasses)
			this.CounterIncrement(classes, "unitsCaptured", type);

		if (costs)
			for (const type in costs)
				this.unitsCapturedValue += costs[type];
	}

	if (cmpCapturedEntityIdentity.HasClass("Structure"))
	{
		for (const type of this.buildingsClasses)
			this.CounterIncrement(classes, "buildingsCaptured", type);

		if (costs)
			for (const type in costs)
				this.buildingsCapturedValue += costs[type];
	}
};

StatisticsTracker.prototype.GetResourceCounts = function()
{
	return Engine.QueryInterface(this.entity, IID_Player)?.GetResourceCounts() ??
		Object.fromEntries(Resources.GetCodes().map(res => [res, 0]));
};

StatisticsTracker.prototype.IncreaseResourceGatheredCounter = function(type, amount, specificType)
{
	this.resourcesGathered[type] += amount;

	if (type == "food" && (specificType == "fruit" || specificType == "grain"))
		this.resourcesGathered.vegetarianFood += amount;
};

StatisticsTracker.prototype.IncreaseResourceUsedCounter = function(type, amount)
{
	this.resourcesUsed[type] += amount;
};

StatisticsTracker.prototype.IncreaseTreasuresCollectedCounter = function()
{
	++this.treasuresCollected;
};

StatisticsTracker.prototype.IncreaseLootCollectedCounter = function(amount)
{
	for (let type in amount)
		this.lootCollected += amount[type];
};

StatisticsTracker.prototype.IncreaseResourcesSoldCounter = function(type, amount)
{
	this.resourcesSold[type] += amount;
};

StatisticsTracker.prototype.IncreaseResourcesBoughtCounter = function(type, amount)
{
	this.resourcesBought[type] += amount;
};

StatisticsTracker.prototype.IncreaseTributesSentCounter = function(amount)
{
	this.tributesSent += amount;
};

StatisticsTracker.prototype.IncreaseTributesReceivedCounter = function(amount)
{
	this.tributesReceived += amount;
};

StatisticsTracker.prototype.IncreaseTradeIncomeCounter = function(amount)
{
	this.tradeIncome += amount;
};

StatisticsTracker.prototype.GetPopulationCount = function()
{
	let cmpPlayer = Engine.QueryInterface(this.entity, IID_Player);
	return cmpPlayer ? cmpPlayer.GetPopulationCount() : 0;
};

StatisticsTracker.prototype.IncreaseSuccessfulBribesCounter = function()
{
	++this.successfulBribes;
};

StatisticsTracker.prototype.IncreaseFailedBribesCounter = function()
{
	++this.failedBribes;
};

StatisticsTracker.prototype.GetPercentMapExplored = function()
{
	let cmpPlayer = Engine.QueryInterface(this.entity, IID_Player);
	if (!cmpPlayer)
		return 0;

	return Engine.QueryInterface(SYSTEM_ENTITY, IID_RangeManager).GetPercentMapExplored(cmpPlayer.GetPlayerID());
};

StatisticsTracker.prototype.GetTeamPercentMapExplored = function()
{
	const cmpDiplomacy = Engine.QueryInterface(this.entity, IID_Diplomacy);
	if (!cmpDiplomacy)
		return 0;

	const team = cmpDiplomacy.GetTeam();
	const cmpRangeManager = Engine.QueryInterface(SYSTEM_ENTITY, IID_RangeManager);
	// If teams are not locked, this statistic won't be displayed, so don't bother computing
	if (team == -1 || !cmpDiplomacy.IsTeamLocked())
	{
		const cmpPlayer = Engine.QueryInterface(this.entity, IID_Player);
		if (!cmpPlayer)
			return 0;
		return cmpRangeManager.GetPercentMapExplored(cmpPlayer.GetPlayerID());
	}

	const teamPlayers = [];
	const numPlayers = Engine.QueryInterface(SYSTEM_ENTITY, IID_PlayerManager).GetNumPlayers();
	for (let i = 1; i < numPlayers; ++i)
		if (QueryPlayerIDInterface(i, IID_Diplomacy)?.GetTeam() === team)
			teamPlayers.push(i);

	return cmpRangeManager.GetUnionPercentMapExplored(teamPlayers);
};

StatisticsTracker.prototype.GetPercentMapControlled = function()
{
	let cmpPlayer = Engine.QueryInterface(this.entity, IID_Player);
	if (!cmpPlayer)
		return 0;

	return Engine.QueryInterface(SYSTEM_ENTITY, IID_TerritoryManager).GetTerritoryPercentage(cmpPlayer.GetPlayerID());
};

StatisticsTracker.prototype.GetTeamPercentMapControlled = function()
{
	const cmpDiplomacy = Engine.QueryInterface(this.entity, IID_Diplomacy);
	if (!cmpDiplomacy)
		return 0;

	const team = cmpDiplomacy.GetTeam();
	const cmpTerritoryManager = Engine.QueryInterface(SYSTEM_ENTITY, IID_TerritoryManager);
	if (team === -1 || !cmpDiplomacy.IsTeamLocked())
	{
		let cmpPlayer = Engine.QueryInterface(this.entity, IID_Player);
		if (!cmpPlayer)
			return 0;
		return cmpTerritoryManager.GetTerritoryPercentage(cmpPlayer.GetPlayerID());
	}

	let teamPercent = 0;
	const numPlayers = Engine.QueryInterface(SYSTEM_ENTITY, IID_PlayerManager).GetNumPlayers();
	for (let i = 1; i < numPlayers; ++i)
		if (QueryPlayerIDInterface(i, IID_Diplomacy)?.GetTeam() === team)
			teamPercent += cmpTerritoryManager.GetTerritoryPercentage(i);

	return teamPercent;
};

StatisticsTracker.prototype.OnTerritoriesChanged = function(msg)
{
	this.UpdatePeakPercentages();
};

StatisticsTracker.prototype.OnGlobalPlayerDefeated = function(msg)
{
	this.UpdatePeakPercentages();
};

StatisticsTracker.prototype.OnGlobalPlayerWon = function(msg)
{
	this.UpdatePeakPercentages();
};

StatisticsTracker.prototype.UpdatePeakPercentages = function()
{
	this.peakPercentMapControlled = Math.max(this.peakPercentMapControlled, this.GetPercentMapControlled());
	this.teamPeakPercentMapControlled = Math.max(this.teamPeakPercentMapControlled, this.GetTeamPercentMapControlled());
};

StatisticsTracker.prototype.PushValue = function(fromData, toData)
{
	if (typeof fromData == "object")
		for (let prop in fromData)
		{
			if (typeof toData[prop] != "object")
				toData[prop] = [fromData[prop]];
			else
				this.PushValue(fromData[prop], toData[prop]);
		}
	else
		toData.push(fromData);
};

StatisticsTracker.prototype.UpdateSequences = function()
{
	if (!this.sequences)
		this.OnGlobalInitGame();

	let cmpTimer = Engine.QueryInterface(SYSTEM_ENTITY, IID_Timer);
	this.sequences.time.push(cmpTimer.GetTime() / 1000);
	this.PushValue(this.GetStatistics(), this.sequences);
};

Engine.RegisterComponentType(IID_StatisticsTracker, "StatisticsTracker", StatisticsTracker);
