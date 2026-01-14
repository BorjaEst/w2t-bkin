"""Unit tests for pose metadata Pydantic models.

Tests the PoseMetadata, PoseCamera, PoseMapping, and PoseSkeleton models
for validation and structure.
"""

from pydantic import ValidationError
import pytest

from w2t_bkin.models import PoseCamera, PoseMapping, PoseMetadata, PoseSkeleton, SkeletonEdge, SkeletonNode


class TestPoseCamera:
    """Test PoseCamera model validation."""

    def test_valid_dlc_camera(self):
        """Test valid DLC camera configuration."""
        camera = PoseCamera(camera_id="camera_0", source="dlc", h5_path="dlc-pose/camera_0.h5")
        assert camera.camera_id == "camera_0"
        assert camera.source == "dlc"
        assert camera.h5_path == "dlc-pose/camera_0.h5"
        assert camera.mapping_id is None
        assert camera.skeleton_id is None

    def test_valid_sleap_camera(self):
        """Test valid SLEAP camera configuration."""
        camera = PoseCamera(camera_id="camera_1", source="sleap", h5_path="sleap-pose/camera_1.h5")
        assert camera.source == "sleap"

    def test_camera_with_mapping_id(self):
        """Test camera with mapping_id."""
        camera = PoseCamera(camera_id="camera_0", source="dlc", h5_path="dlc-pose/camera_0.h5", mapping_id="canonical_mouse")
        assert camera.mapping_id == "canonical_mouse"

    def test_camera_with_skeleton_id(self):
        """Test camera with skeleton_id."""
        camera = PoseCamera(camera_id="camera_0", source="dlc", h5_path="dlc-pose/camera_0.h5", skeleton_id="mouse_bodyparts")
        assert camera.skeleton_id == "mouse_bodyparts"

    def test_invalid_source_raises_error(self):
        """Test that invalid source raises ValidationError."""
        with pytest.raises(ValidationError):
            PoseCamera(camera_id="camera_0", source="invalid_source", h5_path="pose/camera_0.h5")

    def test_missing_required_fields_raises_error(self):
        """Test that missing required fields raises ValidationError."""
        with pytest.raises(ValidationError):
            PoseCamera(camera_id="camera_0", source="dlc")  # Missing h5_path

    def test_extra_fields_forbidden(self):
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError):
            PoseCamera(camera_id="camera_0", source="dlc", h5_path="dlc-pose/camera_0.h5", extra_field="not_allowed")


class TestPoseMapping:
    """Test PoseMapping model validation."""

    def test_valid_mapping(self):
        """Test valid pose mapping."""
        mapping = PoseMapping(id="canonical_mouse", description="DLC to canonical names", map={"nose": "snout", "leftear": "ear_left"})
        assert mapping.id == "canonical_mouse"
        assert mapping.description == "DLC to canonical names"
        assert mapping.map == {"nose": "snout", "leftear": "ear_left"}

    def test_mapping_without_description(self):
        """Test mapping without optional description."""
        mapping = PoseMapping(id="canonical_mouse", map={"nose": "snout"})
        assert mapping.description is None

    def test_empty_map_valid(self):
        """Test that empty map is valid."""
        mapping = PoseMapping(id="empty", map={})
        assert mapping.map == {}

    def test_missing_id_raises_error(self):
        """Test that missing id raises ValidationError."""
        with pytest.raises(ValidationError):
            PoseMapping(map={"nose": "snout"})

    def test_missing_map_raises_error(self):
        """Test that missing map raises ValidationError."""
        with pytest.raises(ValidationError):
            PoseMapping(id="canonical_mouse")


class TestSkeletonNode:
    """Test SkeletonNode model validation."""

    def test_valid_node(self):
        """Test valid skeleton node."""
        node = SkeletonNode(name="snout")
        assert node.name == "snout"

    def test_missing_name_raises_error(self):
        """Test that missing name raises ValidationError."""
        with pytest.raises(ValidationError):
            SkeletonNode()


class TestSkeletonEdge:
    """Test SkeletonEdge model validation."""

    def test_valid_edge(self):
        """Test valid skeleton edge."""
        edge = SkeletonEdge(source="snout", target="body_center")
        assert edge.source == "snout"
        assert edge.target == "body_center"

    def test_missing_source_raises_error(self):
        """Test that missing source raises ValidationError."""
        with pytest.raises(ValidationError):
            SkeletonEdge(target="body_center")

    def test_missing_target_raises_error(self):
        """Test that missing target raises ValidationError."""
        with pytest.raises(ValidationError):
            SkeletonEdge(source="snout")


class TestPoseSkeleton:
    """Test PoseSkeleton model validation."""

    def test_valid_skeleton_with_edges(self):
        """Test valid skeleton with nodes and edges."""
        skeleton = PoseSkeleton(
            id="mouse_bodyparts",
            name="Mouse Full Body",
            description="Standard mouse skeleton",
            nodes=[
                SkeletonNode(name="snout"),
                SkeletonNode(name="body_center"),
                SkeletonNode(name="tail_base"),
            ],
            edges=[
                SkeletonEdge(source="snout", target="body_center"),
                SkeletonEdge(source="body_center", target="tail_base"),
            ],
        )
        assert skeleton.id == "mouse_bodyparts"
        assert skeleton.name == "Mouse Full Body"
        assert len(skeleton.nodes) == 3
        assert len(skeleton.edges) == 2

    def test_skeleton_without_edges(self):
        """Test skeleton without optional edges."""
        skeleton = PoseSkeleton(id="mouse_bodyparts", name="Mouse Full Body", nodes=[SkeletonNode(name="snout")])
        assert skeleton.edges is None

    def test_skeleton_without_description(self):
        """Test skeleton without optional description."""
        skeleton = PoseSkeleton(id="mouse_bodyparts", name="Mouse Full Body", nodes=[SkeletonNode(name="snout")])
        assert skeleton.description is None

    def test_empty_nodes_list_valid(self):
        """Test that empty nodes list raises error (at least one node required conceptually)."""
        # Note: Pydantic allows empty list, but semantically should have at least one node
        skeleton = PoseSkeleton(id="empty_skeleton", name="Empty", nodes=[])
        assert len(skeleton.nodes) == 0

    def test_missing_required_fields_raises_error(self):
        """Test that missing required fields raises ValidationError."""
        with pytest.raises(ValidationError):
            PoseSkeleton(id="mouse_bodyparts", name="Mouse Full Body")  # Missing nodes


class TestPoseMetadata:
    """Test PoseMetadata model validation."""

    def test_valid_complete_metadata(self):
        """Test valid complete pose metadata."""
        metadata = PoseMetadata(
            cameras=[PoseCamera(camera_id="camera_0", source="dlc", h5_path="dlc-pose/camera_0.h5", mapping_id="canonical", skeleton_id="mouse")],
            mappings=[PoseMapping(id="canonical", map={"nose": "snout"})],
            skeletons=[PoseSkeleton(id="mouse", name="Mouse", nodes=[SkeletonNode(name="snout")])],
        )
        assert len(metadata.cameras) == 1
        assert len(metadata.mappings) == 1
        assert len(metadata.skeletons) == 1

    def test_empty_metadata_valid(self):
        """Test that empty metadata (all defaults) is valid."""
        metadata = PoseMetadata()
        assert metadata.cameras == []
        assert metadata.mappings == []
        assert metadata.skeletons == []

    def test_metadata_with_only_cameras(self):
        """Test metadata with only cameras (no mappings/skeletons)."""
        metadata = PoseMetadata(cameras=[PoseCamera(camera_id="camera_0", source="dlc", h5_path="dlc-pose/camera_0.h5")])
        assert len(metadata.cameras) == 1
        assert metadata.mappings == []
        assert metadata.skeletons == []

    def test_metadata_from_dict(self):
        """Test creating PoseMetadata from dict (as loaded from TOML)."""
        metadata_dict = {
            "cameras": [
                {
                    "camera_id": "camera_0",
                    "source": "dlc",
                    "h5_path": "dlc-pose/camera_0.h5",
                }
            ],
            "mappings": [{"id": "canonical", "map": {"nose": "snout"}}],
            "skeletons": [{"id": "mouse", "name": "Mouse", "nodes": [{"name": "snout"}]}],
        }
        metadata = PoseMetadata(**metadata_dict)
        assert len(metadata.cameras) == 1
        assert metadata.cameras[0].camera_id == "camera_0"
        assert len(metadata.mappings) == 1
        assert metadata.mappings[0].id == "canonical"
        assert len(metadata.skeletons) == 1
        assert metadata.skeletons[0].id == "mouse"

    def test_invalid_camera_in_list_raises_error(self):
        """Test that invalid camera in cameras list raises ValidationError."""
        with pytest.raises(ValidationError):
            PoseMetadata(cameras=[{"camera_id": "camera_0", "source": "invalid_source", "h5_path": "pose/camera_0.h5"}])

    def test_extra_fields_forbidden(self):
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError):
            PoseMetadata(cameras=[], mappings=[], skeletons=[], extra_field="not_allowed")
