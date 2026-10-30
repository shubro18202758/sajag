import React, { createContext, useContext, useState, useCallback, useRef, useEffect, useMemo } from 'react';
import * as api from '../services/api';

const ConvoyContext = createContext(null);

export function useConvoy() {
  const ctx = useContext(ConvoyContext);
  if (!ctx) throw new Error('useConvoy must be used within ConvoyProvider');
  return ctx;
}

/**
 * Convoy lifecycle states: idle → planning → approved → active → completed
 */
export function ConvoyProvider({ children }) {
  // ─── Convoy lifecycle ──────────────────────────────────────────
  const [movementId, setMovementId] = useState(null);
  const [lifecycle, setLifecycle] = useState('idle'); // idle | planning | approved | active | completed
  const [planResult, setPlanResult] = useState(null);
  const [escortResult, setEscortResult] = useState(null);
  const [clearResult, setClearResult] = useState(null);
  const [lifecycleError, setLifecycleError] = useState(null);

  // ─── Global data ───────────────────────────────────────────────
  const [corridorSummary, setCorridorSummary] = useState(null);
  const [activeMovements, setActiveMovements] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [gpuHealth, setGpuHealth] = useState(null);
  const [backendHealth, setBackendHealth] = useState(null);

  // ─── AI reasoning log ──────────────────────────────────────────
  const [aiReasoning, setAiReasoning] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatStreaming, setChatStreaming] = useState(false);

  const addReasoning = useCallback((entry) => {
    setAiReasoning((prev) => [{ ...entry, timestamp: Date.now() }, ...prev].slice(0, 50));
  }, []);

  // ─── Blue Book ASL Pre-Deployment Checklist ────────────────────
  const [aslChecklist, setAslChecklist] = useState({
    asl_meeting:      false,  // ASL multi-agency meeting (SPG, DGP/SSP, DM, IB)
    route_finalised:  false,  // Route finalisation complete
    vuln_points:      false,  // Vulnerable points identified
    contingency_route:false,  // Contingency (Plan B) route planned & sanitised
    threat_briefing:  false,  // Threat intelligence briefing
    comms_protocol:   false,  // Communication protocols established
    route_survey:     false,  // Physical route survey (culverts/bridges/drains)
    antisab_sweep:    false,  // Anti-sabotage sweep (sniffer dogs, DFMD, explosive det.)
    vehicles_cleared: false,  // Unmarked vehicles removed from route
    vehicle_checks:   false,  // Convoy vehicle mechanical + anti-sabotage checks
    driver_vetting:   false,  // Driver antecedents verified, speed sync briefed
    flag_mounted:     false,  // National Flag fender-mounted on VVIP vehicle
  });

  // ─── Blue Book 10-Rule Protocol Compliance ─────────────────────
  const [protocolCompliance, setProtocolCompliance] = useState({
    r1_state_responsibility: true,   // Rule 1: State Govt. responsibility acknowledged
    r2_police_arrangements:  false,  // Rule 2: State police protective arrangements in place
    r3_no_stop_rule:         true,   // Rule 3: Convoy will not stop until destination
    r4_dgp_chief_sec:        false,  // Rule 4: DGP + Chief Sec. present on VVIP arrival
    r5_contingency_rehearsed:false,  // Rule 5: Contingency plans exercised via physical rehearsal
    r6_same_make_vehicles:   false,  // Rule 6: All convoy vehicles same make/colour
    r7_spg_director_clearance:false, // Rule 7: SPG Director explicit clearance
    r8_realtime_updates:     false,  // Rule 8: State police → SPG real-time updates active
    r9_security_faces_crowd: true,   // Rule 9: Security personnel face crowd, not VVIP
    r10_incidents_logged:    true,   // Rule 10: All incidents formally logged
  });

  // ─── Anti-Sabotage Framework Status (Blue Book §6) ────────────
  const [antiSabotage, setAntiSabotage] = useState({
    physical_search: false,  // Visual + manual inspection of persons, vehicles, spaces
    technical_gadgets: false, // DFMD, HHMD, explosive detectors, mine sweepers
    sniffer_dogs: false,     // Trained dogs for explosive/contraband detection
  });

  // ─── ECM / Transit Protocol Status ─────────────────────────────
  const [transitStatus, setTransitStatus] = useState({
    ecm_active: false,       // Electronic countermeasures (ECM/jamming) active
    spg_clearance: false,    // SPG Director clearance received
    route_sanitised: false,  // State police have sanitised the route
    formation_intact: true,  // Convoy box formation integrity
  });

  // ─── Blue Book §3.5 — Plan B Contingency System ─────────────────
  const [planB, setPlanB] = useState({
    active: false,                    // Plan B currently activated
    altRouteSanitised: false,         // Alternate route swept & personnel posted
    altRouteRehearsed: false,         // Physical trial run completed during ASL
    contingencyMotorcadeReady: false, // Backup convoy formation at halting location
    transportFallback: false,         // Road fallback if heli/air unavailable
    nearestHospital: null,            // { name, distance_km, eta_min, coords }
    nearestSafeHouse: null,           // { name, distance_km, eta_min, coords }
    emergencyFacilities: [],          // Array of { type, name, distance_km, coords }
    activatedAt: null,                // Timestamp when Plan B was triggered
    reason: null,                     // Why Plan B was activated
  });

  // Emergency facilities along the Mumbai demo corridor (Mantralaya → Airport T2); hospitals from the
  // City Pack's landmarks, the secure points and helipads fictional (demo only)
  const EMERGENCY_FACILITIES = useMemo(() => [
    { type: 'hospital', name: 'Nair Hospital', distance_km: 1.8, eta_min: 4, coords: [18.972, 72.824] },
    { type: 'hospital', name: 'KEM Hospital', distance_km: 2.5, eta_min: 5, coords: [19.0026, 72.842] },
    { type: 'hospital', name: 'Cooper Hospital', distance_km: 3.2, eta_min: 6, coords: [19.108, 72.837] },
    { type: 'safe_house', name: 'Secure Point Alpha (demo)', distance_km: 1.1, eta_min: 3, coords: [18.9440, 72.8250] },
    { type: 'safe_house', name: 'Secure Point Bravo (demo)', distance_km: 2.4, eta_min: 5, coords: [19.0100, 72.8180] },
    { type: 'safe_house', name: 'Secure Point Charlie (demo)', distance_km: 4.0, eta_min: 7, coords: [19.0700, 72.8520] },
    { type: 'helipad', name: 'Mumbai Airport Helipad', distance_km: 8.5, eta_min: 14, coords: [19.0989, 72.8746] },
    { type: 'helipad', name: 'Racecourse Helipad (demo)', distance_km: 0.5, eta_min: 2, coords: [18.9830, 72.8190] },
  ], []);

  const activatePlanB = useCallback((reason = 'Manual activation') => {
    const nearest = (type) => EMERGENCY_FACILITIES.filter(f => f.type === type)
      .sort((a, b) => a.distance_km - b.distance_km)[0] || null;
    setPlanB(prev => ({
      ...prev,
      active: true,
      activatedAt: Date.now(),
      reason,
      nearestHospital: nearest('hospital'),
      nearestSafeHouse: nearest('safe_house'),
      emergencyFacilities: EMERGENCY_FACILITIES,
    }));
    addReasoning({ type: 'critical', title: 'PLAN B ACTIVATED', detail: `Contingency protocol triggered: ${reason}. Nearest hospital: ${nearest('hospital')?.name}. Safe house: ${nearest('safe_house')?.name}.` });
  }, [EMERGENCY_FACILITIES, addReasoning]);

  const deactivatePlanB = useCallback(() => {
    setPlanB(prev => ({ ...prev, active: false, activatedAt: null, reason: null }));
    addReasoning({ type: 'system', title: 'Plan B Deactivated', detail: 'Contingency protocol stood down. Resuming primary route operations.' });
  }, [addReasoning]);

  const simulatePlanBReadiness = useCallback(() => {
    setPlanB(prev => ({
      ...prev,
      altRouteSanitised: true,
      altRouteRehearsed: true,
      contingencyMotorcadeReady: true,
      transportFallback: true,
      emergencyFacilities: EMERGENCY_FACILITIES,
      nearestHospital: EMERGENCY_FACILITIES.find(f => f.type === 'hospital'),
      nearestSafeHouse: EMERGENCY_FACILITIES.find(f => f.type === 'safe_house'),
    }));
  }, [EMERGENCY_FACILITIES]);

  // ─── Backend protocol sync (debounced) ─────────────────────────
  const protocolSyncTimerRef = useRef(null);

  const syncProtocolToBackend = useCallback((update) => {
    if (!movementId) return;
    if (protocolSyncTimerRef.current) clearTimeout(protocolSyncTimerRef.current);
    protocolSyncTimerRef.current = setTimeout(() => {
      api.updateProtocolState(movementId, update).catch(() => {});
    }, 500);
  }, [movementId]);

  // Sync ASL changes to backend
  useEffect(() => {
    if (movementId && lifecycle !== 'idle') {
      syncProtocolToBackend({ asl_checklist: aslChecklist });
    }
  }, [aslChecklist, movementId, lifecycle, syncProtocolToBackend]);

  // Sync protocol compliance to backend
  useEffect(() => {
    if (movementId && lifecycle !== 'idle') {
      syncProtocolToBackend({ protocol_compliance: protocolCompliance });
    }
  }, [protocolCompliance, movementId, lifecycle, syncProtocolToBackend]);

  // Sync anti-sabotage to backend
  useEffect(() => {
    if (movementId && lifecycle !== 'idle') {
      syncProtocolToBackend({ anti_sabotage: antiSabotage });
    }
  }, [antiSabotage, movementId, lifecycle, syncProtocolToBackend]);

  // Sync transit status to backend
  useEffect(() => {
    if (movementId && lifecycle !== 'idle') {
      syncProtocolToBackend({ transit_status: transitStatus });
    }
  }, [transitStatus, movementId, lifecycle, syncProtocolToBackend]);

  // ─── AI-powered protocol actions ──────────────────────────────
  const [protocolAssessment, setProtocolAssessment] = useState(null);
  const [assessingProtocol, setAssessingProtocol] = useState(false);
  const [securityDossier, setSecurityDossier] = useState(null);
  const [generatingDossier, setGeneratingDossier] = useState(false);
  const [threatBrief, setThreatBrief] = useState(null);
  const [assessingThreat, setAssessingThreat] = useState(false);

  const runProtocolAssessment = useCallback(async () => {
    if (!movementId) return;
    setAssessingProtocol(true);
    addReasoning({ type: 'thought', title: 'Protocol Assessment', detail: 'Qwen 3.5 analyzing Blue Book compliance...' });
    try {
      const res = await api.assessProtocol(movementId);
      setProtocolAssessment(res.data?.assessment);
      addReasoning({
        type: 'decision',
        title: 'Protocol Assessment Complete',
        detail: `Confidence: ${res.data?.assessment?.confidence || 'N/A'}`,
        data: res.data?.assessment,
      });
      return res.data;
    } catch (err) {
      addReasoning({ type: 'error', title: 'Assessment Failed', detail: err.message });
      throw err;
    } finally {
      setAssessingProtocol(false);
    }
  }, [movementId, addReasoning]);

  const runDossierGeneration = useCallback(async (params = {}) => {
    if (!movementId) return;
    setGeneratingDossier(true);
    addReasoning({ type: 'thought', title: 'Dossier Generation', detail: 'Qwen 3.5 generating comprehensive security dossier...' });
    try {
      const res = await api.generateDossier(movementId, {
        vvip_class: params.vvipClass || planResult?.vvip_class || 'Z',
        origin_name: params.originName || null,
        destination_name: params.destinationName || null,
        include_sections: params.sections || null,
      });
      setSecurityDossier(res.data?.dossier);
      addReasoning({
        type: 'decision',
        title: 'Security Dossier Generated',
        detail: `${Object.keys(res.data?.dossier || {}).length} sections produced by Qwen 3.5`,
        data: res.data?.dossier,
      });
      return res.data;
    } catch (err) {
      addReasoning({ type: 'error', title: 'Dossier Failed', detail: err.message });
      throw err;
    } finally {
      setGeneratingDossier(false);
    }
  }, [movementId, planResult, addReasoning]);

  const runThreatAssessment = useCallback(async () => {
    if (!movementId) return;
    setAssessingThreat(true);
    addReasoning({ type: 'thought', title: 'Threat Assessment', detail: 'Qwen 3.5 analyzing real-time threat environment...' });
    try {
      const res = await api.getThreatAssessment(movementId);
      setThreatBrief(res.data?.threat);
      // Update local threat level from AI assessment
      const level = res.data?.threat?.data?.threat_level || res.data?.threat?.threat_level;
      if (level) {
        setPlanB(prev => ({ ...prev })); // force re-render
      }
      addReasoning({
        type: res.data?.threat?.data?.threat_level === 'critical' ? 'critical' : 'decision',
        title: 'Threat Assessment',
        detail: `Threat Level: ${level || 'assessed'}`,
        data: res.data?.threat,
      });
      return res.data;
    } catch (err) {
      addReasoning({ type: 'error', title: 'Threat Assessment Failed', detail: err.message });
      throw err;
    } finally {
      setAssessingThreat(false);
    }
  }, [movementId, addReasoning]);

  // ─── Map interaction state (shared between map ↔ sidebars) ─────
  const [mapSegments, setMapSegments] = useState([]);
  const [selectedSegmentId, setSelectedSegmentId] = useState(null);
  const [mapFlyTarget, setMapFlyTarget] = useState(null);
  const [tempOriginCoords, setTempOriginCoords] = useState(null);   // [lon, lat]
  const [tempDestCoords, setTempDestCoords] = useState(null);       // [lon, lat]
  const [highlightedSegments, setHighlightedSegments] = useState([]); // segment IDs to pulse-highlight

  // ─── Convoy simulation engine ──────────────────────────────────
  const [convoySimulation, setConvoySimulation] = useState(null);
  // Shape: { active, routeCoords:[[lat,lng],...], currentIndex, progress(0-1),
  //   position:{lat,lng}, heading, speed, startTime, totalDistanceM,
  //   distanceTraveledM, etaSeconds, segmentIds:[], currentSegmentIdx,
  //   speedHistory:[], congestionHistory:[], etaHistory:[], paused }
  const simIntervalRef = useRef(null);
  const simStateRef = useRef(null); // for mutable access inside interval
  const demoStartedRef = useRef(false);

  // Haversine distance in meters
  const haversine = useCallback((lat1, lon1, lat2, lon2) => {
    const R = 6371000;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }, []);

  // Bearing between two points in degrees
  const bearing = useCallback((lat1, lon1, lat2, lon2) => {
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const y = Math.sin(dLon) * Math.cos(lat2 * Math.PI / 180);
    const x = Math.cos(lat1 * Math.PI / 180) * Math.sin(lat2 * Math.PI / 180) -
              Math.sin(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.cos(dLon);
    return ((Math.atan2(y, x) * 180 / Math.PI) + 360) % 360;
  }, []);

  // ─── ASL Checklist Helpers ─────────────────────────────────────
  const toggleAslItem = useCallback((key) => {
    setAslChecklist(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const aslReadiness = useMemo(() => {
    const items = Object.values(aslChecklist);
    const checked = items.filter(Boolean).length;
    return { checked, total: items.length, pct: Math.round((checked / items.length) * 100), ready: checked === items.length };
  }, [aslChecklist]);

  // Critical ASL items that MUST be checked before deploy
  const aslCriticalReady = useMemo(() => {
    return aslChecklist.asl_meeting && aslChecklist.route_finalised && aslChecklist.route_survey && aslChecklist.antisab_sweep && aslChecklist.vehicle_checks && aslChecklist.driver_vetting;
  }, [aslChecklist]);

  // Auto-simulate ASL completion during demo
  const simulateAslCompletion = useCallback(() => {
    const keys = Object.keys(aslChecklist);
    let delay = 0;
    keys.forEach((key) => {
      delay += 400 + Math.random() * 300;
      setTimeout(() => {
        setAslChecklist(prev => ({ ...prev, [key]: true }));
      }, delay);
    });
    // After all items checked, auto-set anti-sabotage and transit
    setTimeout(() => {
      setAntiSabotage({ physical_search: true, technical_gadgets: true, sniffer_dogs: true });
      setTransitStatus(prev => ({ ...prev, route_sanitised: true, spg_clearance: true }));
      simulatePlanBReadiness();
      setProtocolCompliance(prev => ({
        ...prev,
        r2_police_arrangements: true,
        r5_contingency_rehearsed: true,
        r6_same_make_vehicles: true,
        r7_spg_director_clearance: true,
        r8_realtime_updates: true,
      }));
      addReasoning({ type: 'system', title: 'ASL Complete', detail: 'All 12 Blue Book pre-deployment checks verified. SPG Director clearance granted.' });
    }, delay + 600);
  }, [aslChecklist, addReasoning, simulatePlanBReadiness]);

  const toggleProtocolRule = useCallback((key) => {
    setProtocolCompliance(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const protocolScore = useMemo(() => {
    const items = Object.values(protocolCompliance);
    const checked = items.filter(Boolean).length;
    return { checked, total: items.length, pct: Math.round((checked / items.length) * 100) };
  }, [protocolCompliance]);

  const startConvoySimulation = useCallback((routeSegmentIds) => {
    // Build ordered polyline from segment geometries
    const segs = routeSegmentIds
      .map(sid => mapSegments.find(s => String(s.segment_id) === String(sid)))
      .filter(s => s?.geometry?.coordinates?.length);
    if (segs.length === 0) return;

    const routeCoords = [];
    for (const seg of segs) {
      for (const c of seg.geometry.coordinates) {
        routeCoords.push([c[1], c[0]]); // [lat, lng]
      }
    }
    if (routeCoords.length < 2) return;

    // Compute cumulative distances
    const cumDist = [0];
    for (let i = 1; i < routeCoords.length; i++) {
      cumDist.push(cumDist[i - 1] + haversine(routeCoords[i - 1][0], routeCoords[i - 1][1], routeCoords[i][0], routeCoords[i][1]));
    }
    const totalDistanceM = cumDist[cumDist.length - 1];

    const initState = {
      active: true,
      paused: false,
      routeCoords,
      cumDist,
      currentIndex: 0,
      progress: 0,
      position: { lat: routeCoords[0][0], lng: routeCoords[0][1] },
      heading: bearing(routeCoords[0][0], routeCoords[0][1], routeCoords[1][0], routeCoords[1][1]),
      speed: 35 + Math.random() * 15, // 35-50 km/h initial
      startTime: Date.now(),
      totalDistanceM,
      distanceTraveledM: 0,
      etaSeconds: totalDistanceM / (40 * 1000 / 3600), // initial estimate at 40km/h
      segmentIds: routeSegmentIds,
      currentSegmentIdx: 0,
      speedHistory: [],
      congestionHistory: [],
      etaHistory: [],
      trailCoords: [{ lat: routeCoords[0][0], lng: routeCoords[0][1], speed: 40, congestion: 0.2 }],
      // Enhanced tracking
      maxSpeed: 0,
      minSpeed: 999,
      avgSpeed: 0,
      speedSamples: 0,
      acceleration: 0,        // km/h per tick (+accel, -decel)
      prevSpeed: 40,
      originCoord: { lat: routeCoords[0][0], lng: routeCoords[0][1] },
      destCoord: { lat: routeCoords[routeCoords.length - 1][0], lng: routeCoords[routeCoords.length - 1][1] },
      elapsedSeconds: 0,
      segmentsTraversed: 0,
      // R2 enhancements
      fuelPct: 100,                 // simulated fuel 100→0
      distanceRemainingM: totalDistanceM,
      currentZone: 'primary',       // road class of current segment
      threatLevel: 'nominal',       // nominal | guarded | moderate | elevated | critical
      gForce: 0,                    // lateral G-force from heading delta
      prevHeading: 0,
      zoneLog: [],                  // [{time, fromZone, toZone, segId}]
      signalsRemaining: Math.max(2, Math.floor(segs.length * 0.3)), // ~30% of segments have signals
      routeSegments: segs,
    };

    simStateRef.current = initState;
    setConvoySimulation({ ...initState });

    addReasoning({ type: 'system', title: 'Convoy Simulation Started', detail: `${routeSegmentIds.length} segments, ${(totalDistanceM / 1000).toFixed(1)} km route` });

    // Clear any existing interval
    if (simIntervalRef.current) clearInterval(simIntervalRef.current);

    // Animation tick — every 200ms, advance convoy position
    simIntervalRef.current = setInterval(() => {
      const st = simStateRef.current;
      if (!st || !st.active || st.paused) return;

      // Speed based on current segment's road class + congestion influence + jitter
      const segProg = st.distanceTraveledM / Math.max(1, st.totalDistanceM);
      const curSegIdx = Math.min(Math.floor(segProg * st.segmentIds.length), st.segmentIds.length - 1);
      const curSeg = st.routeSegments?.[curSegIdx];
      const segSpeedLimit = curSeg?.speed_limit_kmh || curSeg?.properties?.speed_limit_kmh || 40;
      const segRdClass = curSeg?.road_class || curSeg?.properties?.road_class || 'primary';
      const rdClassSpeedMap = { motorway: 80, trunk: 60, primary: 45, secondary: 35, tertiary: 30, residential: 25, service: 20 };
      const rdBaseSpeed = rdClassSpeedMap[segRdClass] || segSpeedLimit;
      // Smooth oscillation around road-class speed ± 12%, with micro-jitter
      const jitter = (Math.random() - 0.5) * 6;
      const speed = Math.max(5, Math.min(80, rdBaseSpeed + rdBaseSpeed * 0.12 * Math.sin(Date.now() / 10000) + jitter));
      const speedMps = speed * 1000 / 3600;
      const dt = 0.2; // 200ms intervals
      const advanceM = speedMps * dt * 12; // 12x time multiplier for demo visibility

      let newDist = st.distanceTraveledM + advanceM;
      if (newDist >= st.totalDistanceM) {
        // Convoy reached destination
        const last = st.routeCoords[st.routeCoords.length - 1];
        const finalState = {
          ...st,
          active: false,
          progress: 1,
          position: { lat: last[0], lng: last[1] },
          distanceTraveledM: st.totalDistanceM,
          etaSeconds: 0,
          speed: 0,
        };
        simStateRef.current = finalState;
        setConvoySimulation({ ...finalState });
        clearInterval(simIntervalRef.current);
        simIntervalRef.current = null;
        return;
      }

      // Find position on polyline for newDist
      let segIdx = 0;
      for (let i = 1; i < st.cumDist.length; i++) {
        if (st.cumDist[i] >= newDist) { segIdx = i - 1; break; }
        if (i === st.cumDist.length - 1) segIdx = i - 1;
      }
      const localT = (newDist - st.cumDist[segIdx]) / Math.max(0.001, st.cumDist[segIdx + 1] - st.cumDist[segIdx]);
      const p1 = st.routeCoords[segIdx];
      const p2 = st.routeCoords[segIdx + 1] || p1;
      const lat = p1[0] + (p2[0] - p1[0]) * localT;
      const lng = p1[1] + (p2[1] - p1[1]) * localT;
      const hdg = bearing(p1[0], p1[1], p2[0], p2[1]);

      const now = Date.now();
      const elapsed = (now - st.startTime) / 1000;
      const remaining = st.totalDistanceM - newDist;
      const estimatedEta = speedMps > 0 ? remaining / speedMps / 12 : 9999; // account for 12x multiplier

      // Congestion based on road class of current segment + time-of-day + jitter
      const segProgress = newDist / st.totalDistanceM;
      const currentSegIdx = Math.min(Math.floor(segProgress * st.segmentIds.length), st.segmentIds.length - 1);
      const segRoadClass = st.routeSegments?.[currentSegIdx]?.road_class || st.routeSegments?.[currentSegIdx]?.properties?.road_class || 'primary';
      const congBaseMap = { motorway: 0.10, trunk: 0.18, primary: 0.30, secondary: 0.42, tertiary: 0.50, residential: 0.55, service: 0.35 };
      const congBase = congBaseMap[segRoadClass] ?? 0.30;
      const curHour = new Date().getHours();
      const hourEffect = (curHour >= 8 && curHour <= 10) || (curHour >= 17 && curHour <= 20) ? 0.15 : curHour >= 11 && curHour <= 16 ? 0.05 : -0.05;
      const congestion = Math.max(0.05, Math.min(0.95, congBase + hourEffect + (Math.random() - 0.5) * 0.12));

      // Record history (keep last 60 points = ~12 seconds of demo time)
      const speedHist = [...st.speedHistory, { t: elapsed, speed: Math.round(speed), ts: now }].slice(-60);
      const congHist = [...st.congestionHistory, { t: elapsed, congestion: parseFloat(congestion.toFixed(3)), ts: now }].slice(-60);
      const etaHist = [...st.etaHistory, { t: elapsed, eta: Math.round(estimatedEta), ts: now }].slice(-60);
      const trail = [...st.trailCoords, { lat, lng, speed: Math.round(speed), congestion: parseFloat(congestion.toFixed(3)) }].slice(-200);

      // Enhanced tracking
      const newMax = Math.max(st.maxSpeed, speed);
      const newMin = Math.min(st.minSpeed, speed);
      const newSamples = st.speedSamples + 1;
      const newAvg = (st.avgSpeed * st.speedSamples + speed) / newSamples;
      const accel = speed - (st.prevSpeed || speed);
      const newSegTraversed = currentSegIdx > st.segmentsTraversed ? currentSegIdx : st.segmentsTraversed;

      // R2: Fuel — burns proportional to speed (faster = more fuel)
      const fuelBurnRate = 0.008 + (speed / 60) * 0.015; // 0.8–2.3% per tick at max speed
      const newFuel = Math.max(0, (st.fuelPct || 100) - fuelBurnRate);

      // R2: Distance remaining
      const distRemaining = st.totalDistanceM - newDist;

      // R2: Current road zone from segment data
      const currentSeg = st.routeSegments?.[currentSegIdx];
      const currentZone = currentSeg?.road_class || currentSeg?.properties?.road_class || st.currentZone || 'primary';

      // R2: Zone transition detection
      let zoneLog = st.zoneLog || [];
      if (currentZone !== st.currentZone && st.currentZone) {
        zoneLog = [...zoneLog, {
          time: elapsed,
          fromZone: st.currentZone,
          toZone: currentZone,
          segId: st.segmentIds?.[currentSegIdx],
        }].slice(-20);
      }

      // R2: Threat level — derived from congestion + speed (slow+congested = bad)
      const threatScore = congestion * 0.6 + (1 - Math.min(speed / 50, 1)) * 0.4;
      const threatLevel = threatScore > 0.75 ? 'critical' : threatScore > 0.6 ? 'elevated' : threatScore > 0.45 ? 'moderate' : threatScore > 0.25 ? 'guarded' : 'nominal';

      // R2: G-force from heading change (lateral)
      const headingDelta = Math.abs(hdg - (st.prevHeading || hdg));
      const normalizedDelta = headingDelta > 180 ? 360 - headingDelta : headingDelta;
      const gForce = Math.min(2.0, (normalizedDelta / 45) * (speed / 40)); // scale by turn severity and speed

      // R2: Signals remaining (decrement when crossing signal segments)
      const signalsRemaining = Math.max(0, (st.signalsRemaining || 0) - (currentSegIdx > st.segmentsTraversed ? 0.3 : 0));

      const updated = {
        ...st,
        currentIndex: segIdx,
        progress: newDist / st.totalDistanceM,
        position: { lat, lng },
        heading: hdg,
        speed,
        congestion,
        distanceTraveledM: newDist,
        etaSeconds: estimatedEta,
        currentSegmentIdx: currentSegIdx,
        speedHistory: speedHist,
        congestionHistory: congHist,
        etaHistory: etaHist,
        trailCoords: trail,
        maxSpeed: newMax,
        minSpeed: newMin === 999 ? speed : newMin,
        avgSpeed: newAvg,
        speedSamples: newSamples,
        acceleration: accel,
        prevSpeed: speed,
        elapsedSeconds: elapsed,
        segmentsTraversed: newSegTraversed,
        // R2 fields
        fuelPct: newFuel,
        distanceRemainingM: distRemaining,
        currentZone,
        threatLevel,
        gForce,
        prevHeading: hdg,
        zoneLog,
        signalsRemaining: Math.round(signalsRemaining),
      };
      simStateRef.current = updated;
      setConvoySimulation({ ...updated });
    }, 200);
  }, [mapSegments, haversine, bearing, addReasoning]);

  const stopConvoySimulation = useCallback(() => {
    if (simIntervalRef.current) { clearInterval(simIntervalRef.current); simIntervalRef.current = null; }
    if (simStateRef.current) {
      simStateRef.current = { ...simStateRef.current, active: false, paused: false };
      setConvoySimulation(prev => prev ? { ...prev, active: false, paused: false } : null);
    }
  }, []);

  const pauseConvoySimulation = useCallback(() => {
    if (simStateRef.current) {
      simStateRef.current = { ...simStateRef.current, paused: !simStateRef.current.paused };
      setConvoySimulation(prev => prev ? { ...prev, paused: !prev.paused } : null);
    }
  }, []);

  // ═══════════════════════════════════════════════════════════════════════════
  // REALISTIC DEMO: Mantralaya → Mumbai Airport T2
  // Marine Drive, the Coastal Road, the Worli seaface, the Bandra–Worli Sea Link, Kalanagar and the Western
  // Express Highway (waypoints at City Pack landmarks, interpolated between; not snapped to the road network)
  // Road-class-aware speed / congestion / threat derived from ground conditions
  // ═══════════════════════════════════════════════════════════════════════════
  const startDemoSimulation = useCallback(() => {
    if (simIntervalRef.current) { clearInterval(simIntervalRef.current); simIntervalRef.current = null; }

    /* ─── Route phases: each section of the corridor with road properties ─── */
    const ROUTE_PHASES = [
      {
        road_class: 'primary', speed_limit: 40, zone: 'Marine-Drive', congestion_base: 0.24,
        points: [
          [18.9271, 72.8247],[18.9291, 72.8243],[18.9310, 72.8239],[18.9330, 72.8235],
          [18.9355, 72.8234],[18.9380, 72.8233],[18.9405, 72.8231],[18.9430, 72.8230],
          [18.9454, 72.8211],[18.9477, 72.8192],[18.9501, 72.8174],[18.9524, 72.8155],
        ],
      },
      {
        road_class: 'motorway', speed_limit: 80, zone: 'Coastal-Road', congestion_base: 0.10,
        points: [
          [18.9548, 72.8136],[18.9578, 72.8129],[18.9609, 72.8122],[18.9639, 72.8114],
          [18.9670, 72.8107],[18.9700, 72.8100],[18.9725, 72.8105],[18.9751, 72.8110],
          [18.9776, 72.8115],[18.9802, 72.8120],
        ],
      },
      {
        road_class: 'trunk', speed_limit: 50, zone: 'Worli-Seaface', congestion_base: 0.30,
        points: [
          [18.9827, 72.8125],[18.9862, 72.8128],[18.9896, 72.8131],[18.9931, 72.8134],
          [18.9965, 72.8137],[19.0000, 72.8140],[19.0034, 72.8147],[19.0068, 72.8154],
          [19.0102, 72.8161],[19.0136, 72.8168],
        ],
      },
      {
        road_class: 'motorway', speed_limit: 80, zone: 'Sea-Link', congestion_base: 0.08,
        points: [
          [19.0170, 72.8175],[19.0205, 72.8174],[19.0240, 72.8173],[19.0275, 72.8173],
          [19.0310, 72.8172],[19.0345, 72.8171],[19.0380, 72.8170],[19.0409, 72.8179],
          [19.0437, 72.8188],
        ],
      },
      {
        road_class: 'primary', speed_limit: 40, zone: 'Bandra-Kalanagar', congestion_base: 0.40,
        points: [
          [19.0466, 72.8197],[19.0480, 72.8235],[19.0493, 72.8273],[19.0507, 72.8312],
          [19.0520, 72.8350],[19.0538, 72.8386],[19.0555, 72.8423],[19.0572, 72.8459],
        ],
      },
      {
        road_class: 'trunk', speed_limit: 60, zone: 'WEH', congestion_base: 0.34,
        points: [
          [19.0590, 72.8495],[19.0632, 72.8500],[19.0674, 72.8505],[19.0716, 72.8510],
          [19.0758, 72.8515],[19.0800, 72.8520],[19.0830, 72.8530],[19.0860, 72.8540],
          [19.0890, 72.8550],
        ],
      },
      {
        road_class: 'trunk', speed_limit: 40, zone: 'Airport-Approach', congestion_base: 0.18,
        points: [
          [19.0920, 72.8560],[19.0933, 72.8593],[19.0947, 72.8627],[19.0960, 72.8660],
          [19.0970, 72.8689],[19.0979, 72.8717],
          [19.0989, 72.8746],
        ],
      },
    ];

    // Flatten all phase waypoints into a single polyline + per-point road metadata
    const routeCoords = [];
    const pointMeta = [];
    for (const phase of ROUTE_PHASES) {
      for (const pt of phase.points) {
        routeCoords.push(pt);
        pointMeta.push({ road_class: phase.road_class, speed_limit: phase.speed_limit, zone: phase.zone, congestion_base: phase.congestion_base });
      }
    }
    if (routeCoords.length < 2) return;

    // Cumulative distance array
    const cumDist = [0];
    for (let i = 1; i < routeCoords.length; i++) {
      cumDist.push(cumDist[i - 1] + haversine(routeCoords[i - 1][0], routeCoords[i - 1][1], routeCoords[i][0], routeCoords[i][1]));
    }
    const totalDistanceM = cumDist[cumDist.length - 1];

    // Pre-compute phase boundary distances for intersection slowdown
    const phaseBoundaryDists = [];
    let ptIdx = 0;
    for (let pi = 0; pi < ROUTE_PHASES.length - 1; pi++) {
      ptIdx += ROUTE_PHASES[pi].points.length;
      phaseBoundaryDists.push(cumDist[ptIdx]);
    }

    const segmentIds = routeCoords.map((_, i) => `seg-${i + 1}`);
    const initSpeed = ROUTE_PHASES[0].speed_limit * 0.72;

    const initState = {
      active: true, paused: false, routeCoords, cumDist, pointMeta, phaseBoundaryDists,
      currentIndex: 0, progress: 0,
      position: { lat: routeCoords[0][0], lng: routeCoords[0][1] },
      heading: bearing(routeCoords[0][0], routeCoords[0][1], routeCoords[1][0], routeCoords[1][1]),
      speed: initSpeed, congestion: ROUTE_PHASES[0].congestion_base,
      startTime: Date.now(), totalDistanceM, distanceTraveledM: 0,
      etaSeconds: totalDistanceM / (45 * 1000 / 3600),
      segmentIds, currentSegmentIdx: 0,
      speedHistory: [], congestionHistory: [], etaHistory: [],
      trailCoords: [{ lat: routeCoords[0][0], lng: routeCoords[0][1], speed: initSpeed, congestion: ROUTE_PHASES[0].congestion_base }],
      maxSpeed: 0, minSpeed: 999, avgSpeed: 0, speedSamples: 0,
      acceleration: 0, prevSpeed: initSpeed,
      originCoord: { lat: routeCoords[0][0], lng: routeCoords[0][1] },
      destCoord: { lat: routeCoords[routeCoords.length - 1][0], lng: routeCoords[routeCoords.length - 1][1] },
      elapsedSeconds: 0, segmentsTraversed: 0,
      fuelPct: 100, distanceRemainingM: totalDistanceM,
      currentZone: ROUTE_PHASES[0].zone, threatLevel: 'nominal',
      gForce: 0, prevHeading: 0, zoneLog: [],
      signalsRemaining: ROUTE_PHASES.length * 2, routeSegments: [],
    };

    simStateRef.current = initState;
    setConvoySimulation({ ...initState });
    addReasoning({ type: 'system', title: 'VVIP Demo Route Activated', detail: `Mantralaya → Mumbai Airport T2 · ${(totalDistanceM / 1000).toFixed(1)} km · ${ROUTE_PHASES.length} road phases` });

    // ─── Road-aware animation tick (200 ms) ─────────────────────────────────
    simIntervalRef.current = setInterval(() => {
      const st = simStateRef.current;
      if (!st || !st.active || st.paused) return;

      const now = Date.now();
      const elapsed = (now - st.startTime) / 1000;

      // Current road metadata
      const metaIdx = Math.min(st.currentIndex, st.pointMeta.length - 1);
      const meta = st.pointMeta[metaIdx];

      // Intersection slowdown near phase boundaries (±250 m)
      let intersectionFactor = 1.0;
      for (const bd of st.phaseBoundaryDists) {
        const gap = Math.abs(st.distanceTraveledM - bd);
        if (gap < 250) { intersectionFactor = 0.45 + 0.55 * (gap / 250); break; }
      }

      // Road-class-aware speed: oscillates around speed_limit instead of fixed sine
      const speedCycle = meta.speed_limit * (0.68 + 0.22 * Math.sin(now / 6000));
      const jitter = (Math.random() - 0.5) * 3;
      const speed = Math.max(8, (speedCycle + jitter) * intersectionFactor);
      const speedMps = speed * 1000 / 3600;
      const advanceM = speedMps * 0.2 * 5; // 5× time multiplier (slower than 12× for longer demo)

      let newDist = st.distanceTraveledM + advanceM;
      if (newDist >= st.totalDistanceM) {
        const last = st.routeCoords[st.routeCoords.length - 1];
        const fin = { ...st, active: false, progress: 1, position: { lat: last[0], lng: last[1] }, distanceTraveledM: st.totalDistanceM, etaSeconds: 0, speed: 0 };
        simStateRef.current = fin; setConvoySimulation({ ...fin });
        clearInterval(simIntervalRef.current); simIntervalRef.current = null;
        return;
      }

      // Locate point on polyline
      let segIdx = 0;
      for (let i = 1; i < st.cumDist.length; i++) { if (st.cumDist[i] >= newDist) { segIdx = i - 1; break; } if (i === st.cumDist.length - 1) segIdx = i - 1; }
      const localT = (newDist - st.cumDist[segIdx]) / Math.max(0.001, st.cumDist[segIdx + 1] - st.cumDist[segIdx]);
      const p1 = st.routeCoords[segIdx], p2 = st.routeCoords[segIdx + 1] || p1;
      const lat = p1[0] + (p2[0] - p1[0]) * localT;
      const lng = p1[1] + (p2[1] - p1[1]) * localT;
      const hdg = bearing(p1[0], p1[1], p2[0], p2[1]);

      // Road-class-aware congestion with time-of-day influence
      const demoHour = new Date().getHours();
      const demoPeakFactor = (demoHour >= 8 && demoHour <= 10) || (demoHour >= 17 && demoHour <= 20) ? 0.12 : demoHour >= 11 && demoHour <= 16 ? 0.04 : -0.04;
      const congestion = Math.max(0, Math.min(1, meta.congestion_base + demoPeakFactor + (Math.random() - 0.5) * 0.08));

      const remaining = st.totalDistanceM - newDist;
      const estimatedEta = speedMps > 0 ? remaining / speedMps / 5 : 9999;

      // History buffers (80 points ≈ 16 s real-time for rich charts)
      const speedHist = [...st.speedHistory, { t: elapsed, speed: Math.round(speed), ts: now }].slice(-80);
      const congHist = [...st.congestionHistory, { t: elapsed, congestion: parseFloat(congestion.toFixed(3)), ts: now }].slice(-80);
      const etaHist = [...st.etaHistory, { t: elapsed, eta: Math.round(estimatedEta), ts: now }].slice(-80);
      const trail = [...st.trailCoords, { lat, lng, speed: Math.round(speed), congestion: parseFloat(congestion.toFixed(3)) }].slice(-200);

      // Enhanced statistics
      const newMax = Math.max(st.maxSpeed, speed);
      const newMin = Math.min(st.minSpeed, speed);
      const newSamples = st.speedSamples + 1;
      const newAvg = (st.avgSpeed * st.speedSamples + speed) / newSamples;
      const accel = speed - (st.prevSpeed || speed);
      const newSegTraversed = segIdx > st.segmentsTraversed ? segIdx : st.segmentsTraversed;

      // Fuel — burns proportional to speed (motorway burns more)
      const fuelBurnRate = 0.005 + (speed / 80) * 0.012;
      const newFuel = Math.max(0, (st.fuelPct || 100) - fuelBurnRate);

      // Zone transition detection
      const currentZone = meta.zone;
      let zoneLog = st.zoneLog || [];
      if (currentZone !== st.currentZone && st.currentZone) {
        zoneLog = [...zoneLog, { time: elapsed, fromZone: st.currentZone, toZone: currentZone, segId: segIdx }].slice(-20);
      }

      // Threat level — compound score: congestion + speed deficit + road risk
      const roadRisk = meta.road_class === 'secondary' ? 0.30 : meta.road_class === 'primary' ? 0.15 : meta.road_class === 'trunk' ? 0.08 : 0.03;
      const threatScore = congestion * 0.45 + (1 - Math.min(speed / meta.speed_limit, 1)) * 0.30 + roadRisk;
      const threatLevel = threatScore > 0.72 ? 'critical' : threatScore > 0.58 ? 'elevated' : threatScore > 0.40 ? 'moderate' : threatScore > 0.22 ? 'guarded' : 'nominal';

      // G-force from heading change (lateral)
      const headingDelta = Math.abs(hdg - (st.prevHeading || hdg));
      const normalizedDelta = headingDelta > 180 ? 360 - headingDelta : headingDelta;
      const gForce = Math.min(2.0, (normalizedDelta / 45) * (speed / 40));

      const signalsRemaining = Math.max(0, (st.signalsRemaining || 0) - (segIdx > st.segmentsTraversed ? 0.3 : 0));

      const updated = {
        ...st,
        currentIndex: segIdx, progress: newDist / st.totalDistanceM,
        position: { lat, lng }, heading: hdg, speed, congestion,
        distanceTraveledM: newDist, etaSeconds: estimatedEta, currentSegmentIdx: segIdx,
        speedHistory: speedHist, congestionHistory: congHist, etaHistory: etaHist, trailCoords: trail,
        maxSpeed: newMax, minSpeed: newMin === 999 ? speed : newMin, avgSpeed: newAvg, speedSamples: newSamples,
        acceleration: accel, prevSpeed: speed, elapsedSeconds: elapsed, segmentsTraversed: newSegTraversed,
        fuelPct: newFuel, distanceRemainingM: remaining, currentZone, threatLevel, gForce, prevHeading: hdg,
        zoneLog, signalsRemaining: Math.round(signalsRemaining),
      };
      simStateRef.current = updated;
      setConvoySimulation({ ...updated });
    }, 200);
  }, [haversine, bearing, addReasoning]);

  // Ref kept for potential programmatic use
  const startDemoRef = useRef(startDemoSimulation);
  startDemoRef.current = startDemoSimulation;

  // Cleanup on unmount
  useEffect(() => {
    return () => { if (simIntervalRef.current) clearInterval(simIntervalRef.current); };
  }, []);

  const flyToLocation = useCallback((lat, lng, zoom = 15) => {
    setMapFlyTarget({ lat, lng, zoom, _ts: Date.now() });
  }, []);

  const flyToSegment = useCallback((segmentId) => {
    const seg = mapSegments.find((s) => String(s.segment_id) === String(segmentId));
    if (seg?.geom?.coordinates?.length) {
      const coords = seg.geom.coordinates;
      const mid = coords[Math.floor(coords.length / 2)];
      setSelectedSegmentId(segmentId);
      setMapFlyTarget({ lat: mid[1], lng: mid[0], zoom: 16, _ts: Date.now() });
    }
  }, [mapSegments]);

  const selectSegment = useCallback((segmentId) => {
    setSelectedSegmentId((prev) => (prev === segmentId ? null : segmentId));
  }, []);

  // ─── WebSocket refs ────────────────────────────────────────────
  const wsRefs = useRef(new Map());

  // ─── Polling: corridor, movements, anomalies ──────────────────
  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const [sum, mov, anm] = await Promise.all([
          api.getCorridorSummary().catch(() => null),
          api.getActiveMovements().catch(() => ({ data: { movements: [] } })),
          api.getRecentAnomalies(15).catch(() => ({ data: { anomalies: [] } })),
        ]);
        if (!active) return;
        if (sum?.data) setCorridorSummary(sum.data);
        setActiveMovements(mov.data?.movements || []);
        if (anm.data?.anomalies) {
          setAnomalies(
            anm.data.anomalies.map((a, idx) => ({
              id: a.anomaly_id || idx,
              segment_id: a.segment_id,
              type: a.anomaly_type,
              severity: a.severity,
              tag: a.anomaly_type.toUpperCase().replace(/_/g, ' '),
              message: a.details?.description || `Severity ${a.severity} at segment ${a.segment_id}`,
              time: new Date(a.timestamp_utc).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }),
              timestamp: a.timestamp_utc,
              read: false,
            }))
          );
        }
      } catch { /* silent */ }
    };
    poll();
    const id = setInterval(poll, 12000);
    return () => { active = false; clearInterval(id); };
  }, []);

  // ─── Polling: GPU health ───────────────────────────────────────
  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const res = await api.getGpuHealth();
        if (active) setGpuHealth(res.data);
      } catch { /* silent */ }
    };
    poll();
    const id = setInterval(poll, 10000);
    return () => { active = false; clearInterval(id); };
  }, []);

  // ─── Polling: backend health ───────────────────────────────────
  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const res = await api.getHealth();
        if (active) setBackendHealth(res.data);
      } catch { /* silent */ }
    };
    poll();
    const id = setInterval(poll, 30000);
    return () => { active = false; clearInterval(id); };
  }, []);

  // ─── WebSocket tracking for movements ─────────────────────────
  useEffect(() => {
    activeMovements.forEach((mov) => {
      const mid = mov.movement_id;
      if (!mid || wsRefs.current.has(mid)) return;
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/convoy/${mid}`);
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === 'convoy.position') {
            setActiveMovements((prev) =>
              prev.map((m) =>
                m.movement_id === mid
                  ? { ...m, current_position: { lat: data.payload.position[1], lng: data.payload.position[0] } }
                  : m
              )
            );
          }
        } catch { /* silent */ }
      };
      wsRefs.current.set(mid, ws);
    });
  }, [activeMovements]);

  useEffect(() => {
    return () => {
      wsRefs.current.forEach((ws) => { try { ws.close(); } catch {} });
      wsRefs.current.clear();
    };
  }, []);

  // ─── Lifecycle actions ─────────────────────────────────────────

  const deployMovement = useCallback(async ({ origin, destination, vvipClass, plannedDeparture }) => {
    setLifecycleError(null);
    setLifecycle('planning');
    try {
      // Step 1: Create movement
      const createRes = await api.createMovement({
        origin,
        destination,
        vvip_class: vvipClass,
        planned_departure: plannedDeparture || new Date().toISOString(),
      });
      const mid = createRes.data?.movement_id;
      if (!mid) throw new Error('No movement_id returned');
      setMovementId(mid);

      addReasoning({
        type: 'system',
        title: 'Movement Created',
        detail: `Movement ${mid} created for ${vvipClass} class`,
      });

      // Step 2: Plan movement (7-node LangGraph pre-movement workflow)
      const planRes = await api.planMovement(mid, {
        origin,
        destination,
        vvip_class: vvipClass,
        planned_departure: plannedDeparture || new Date().toISOString(),
      });
      setPlanResult(planRes.data);
      setLifecycle('approved');

      addReasoning({
        type: 'plan',
        title: 'Pre-Movement Plan Complete',
        detail: `Status: ${planRes.data?.status}, Confidence: ${planRes.data?.confidence}`,
        data: planRes.data,
      });

      // Step 3: Load protocol state from backend
      try {
        const protocolRes = await api.getProtocolState(mid);
        const ps = protocolRes.data?.protocol_state;
        if (ps) {
          if (ps.asl_checklist) setAslChecklist(prev => ({ ...prev, ...ps.asl_checklist }));
          if (ps.protocol_compliance) setProtocolCompliance(prev => ({ ...prev, ...ps.protocol_compliance }));
          if (ps.anti_sabotage) setAntiSabotage(prev => ({ ...prev, ...ps.anti_sabotage }));
          if (ps.transit_status) setTransitStatus(prev => ({ ...prev, ...ps.transit_status }));
          if (ps.plan_b) setPlanB(prev => ({ ...prev, ...ps.plan_b }));
        }
      } catch { /* protocol state not yet available — use defaults */ }

      return planRes.data;
    } catch (err) {
      setLifecycleError(err.message || 'Planning failed');
      setLifecycle('idle');
      throw err;
    }
  }, [addReasoning]);

  const startEscort = useCallback(async (destination) => {
    if (!movementId) return;
    setLifecycleError(null);
    try {
      setLifecycle('active');
      const res = await api.startEscort(movementId, { destination });
      setEscortResult(res.data);

      addReasoning({
        type: 'escort',
        title: 'Live Escort Complete',
        detail: `${res.data?.total_iterations} iterations, status: ${res.data?.final_status}`,
        data: res.data,
      });

      return res.data;
    } catch (err) {
      setLifecycleError(err.message || 'Escort failed');
      throw err;
    }
  }, [movementId, addReasoning]);

  const clearMovement = useCallback(async () => {
    if (!movementId) return;
    setLifecycleError(null);
    try {
      const res = await api.clearMovement(movementId);
      setClearResult(res.data);
      setLifecycle('completed');

      addReasoning({
        type: 'clear',
        title: 'Post-Clearance Report',
        detail: `${res.data?.segments_recovered}/${res.data?.total_affected_segments} segments recovered`,
        data: res.data,
      });

      return res.data;
    } catch (err) {
      setLifecycleError(err.message || 'Clearance failed');
      throw err;
    }
  }, [movementId, addReasoning]);

  const resetLifecycle = useCallback(() => {
    setMovementId(null);
    setLifecycle('idle');
    setPlanResult(null);
    setEscortResult(null);
    setClearResult(null);
    setLifecycleError(null);
    setTempOriginCoords(null);
    setTempDestCoords(null);
    setHighlightedSegments([]);
    stopConvoySimulation();
    setConvoySimulation(null);
    // Reset Blue Book state
    setAslChecklist(Object.fromEntries(Object.keys(aslChecklist).map(k => [k, false])));
    setAntiSabotage({ physical_search: false, technical_gadgets: false, sniffer_dogs: false });
    setTransitStatus({ ecm_active: false, spg_clearance: false, route_sanitised: false, formation_intact: true });
    setPlanB({ active: false, altRouteSanitised: false, altRouteRehearsed: false, contingencyMotorcadeReady: false, transportFallback: false, nearestHospital: null, nearestSafeHouse: null, emergencyFacilities: [], activatedAt: null, reason: null });
    setProtocolCompliance(prev => ({
      ...prev,
      r2_police_arrangements: false, r4_dgp_chief_sec: false, r5_contingency_rehearsed: false,
      r6_same_make_vehicles: false, r7_spg_director_clearance: false, r8_realtime_updates: false,
    }));
  }, [stopConvoySimulation, aslChecklist]);

  const highlightSegments = useCallback((segIds, flyToFirst = true) => {
    setHighlightedSegments(segIds || []);
    if (flyToFirst && segIds?.length) flyToSegment(segIds[0]);
  }, [flyToSegment]);

  // ─── Streaming AI chat ─────────────────────────────────────────
  const sendChatMessage = useCallback(async (message, vvipClass = 'Z+') => {
    setChatMessages((prev) => [...prev, { role: 'user', content: message, timestamp: Date.now() }]);
    addReasoning({ type: 'thought', title: 'User Query', detail: message });
    setChatStreaming(true);

    try {
      const response = await api.streamChat({
        message,
        movement_id: movementId || undefined,
        vvip_class: vvipClass,
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullResponse = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const event = JSON.parse(line);
            switch (event.type) {
              case 'token':
                fullResponse += event.data;
                setChatMessages((prev) => {
                  const last = prev[prev.length - 1];
                  if (last?.role === 'assistant' && last?.streaming) {
                    return [...prev.slice(0, -1), { ...last, content: fullResponse }];
                  }
                  return [...prev, { role: 'assistant', content: fullResponse, streaming: true, timestamp: Date.now() }];
                });
                break;
              case 'thought':
                addReasoning({ type: 'thought', title: 'Reasoning', detail: event.data?.text || event.data });
                break;
              case 'tool_call':
                addReasoning({
                  type: 'tool',
                  title: `Tool: ${event.data?.toolName}`,
                  detail: JSON.stringify(event.data?.arguments || {}).slice(0, 200),
                  data: event.data,
                });
                break;
              case 'tool_result':
                addReasoning({
                  type: 'tool',
                  title: `Result: ${event.data?.callId}`,
                  detail: `${event.data?.state} (${event.data?.durationMs}ms)`,
                  data: event.data,
                });
                break;
              case 'done':
                if (fullResponse) {
                  setChatMessages((prev) => {
                    const last = prev[prev.length - 1];
                    if (last?.role === 'assistant') {
                      return [...prev.slice(0, -1), { ...last, streaming: false }];
                    }
                    return prev;
                  });
                  addReasoning({ type: 'decision', title: 'AI Response', detail: fullResponse.slice(0, 300) });
                }
                break;
              case 'error':
                addReasoning({ type: 'error', title: 'Stream Error', detail: event.data?.message || 'Unknown error' });
                break;
            }
          } catch { /* skip malformed line */ }
        }
      }

      // If no streaming tokens came, fall back to non-streaming chat
      if (!fullResponse) {
        try {
          const fallback = await api.sendChat({ message, movement_id: movementId || undefined, vvip_class: vvipClass });
          fullResponse = fallback.data?.response?.reasoning || fallback.data?.response?.action || 'AI response received';
          setChatMessages((prev) => [...prev, { role: 'assistant', content: fullResponse, timestamp: Date.now() }]);
          addReasoning({ type: 'decision', title: 'AI Response', detail: fullResponse.slice(0, 300) });
        } catch { /* silent */ }
      }

      return fullResponse;
    } catch (err) {
      addReasoning({ type: 'error', title: 'Chat Failed', detail: err.message });
      setChatMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${err.message}`, error: true, timestamp: Date.now() }]);
      throw err;
    } finally {
      setChatStreaming(false);
    }
  }, [movementId, addReasoning]);

  const value = {
    // Lifecycle
    movementId,
    lifecycle,
    planResult,
    escortResult,
    clearResult,
    lifecycleError,
    deployMovement,
    startEscort,
    clearMovement,
    resetLifecycle,
    // Global data
    corridorSummary,
    activeMovements,
    anomalies,
    gpuHealth,
    backendHealth,
    // AI
    aiReasoning,
    addReasoning,
    chatMessages,
    chatStreaming,
    sendChatMessage,
    // Map interaction
    mapSegments,
    setMapSegments,
    selectedSegmentId,
    selectSegment,
    mapFlyTarget,
    flyToLocation,
    flyToSegment,
    tempOriginCoords,
    setTempOriginCoords,
    tempDestCoords,
    setTempDestCoords,
    highlightedSegments,
    highlightSegments,
    // Convoy simulation
    convoySimulation,
    startConvoySimulation,
    startDemoSimulation,
    stopConvoySimulation,
    pauseConvoySimulation,
    // Blue Book ASL & Protocol
    aslChecklist,
    toggleAslItem,
    aslReadiness,
    aslCriticalReady,
    simulateAslCompletion,
    protocolCompliance,
    toggleProtocolRule,
    protocolScore,
    antiSabotage,
    setAntiSabotage,
    transitStatus,
    setTransitStatus,
    // Blue Book Plan B
    planB,
    activatePlanB,
    deactivatePlanB,
    simulatePlanBReadiness,
    // AI-powered protocol actions
    protocolAssessment,
    assessingProtocol,
    runProtocolAssessment,
    securityDossier,
    generatingDossier,
    runDossierGeneration,
    threatBrief,
    assessingThreat,
    runThreatAssessment,
  };

  return <ConvoyContext.Provider value={value}>{children}</ConvoyContext.Provider>;
}
